#!/usr/bin/env python3
"""Keyword-to-mood classifier pipeline (Phase 1b). See PIPELINE.md."""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder, RobustScaler
from sklearn.svm import SVC

# Non-interactive backend for saving plots without display
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

from src.constants import MOODS


def load_labeled_keywords(tsv_path: Path) -> pd.DataFrame:
    """Load and validate labeled keyword TSV. Schema: see INPUT.md."""
    if not tsv_path.exists():
        raise FileNotFoundError(f"Labeled TSV not found: {tsv_path}")

    df = pd.read_csv(tsv_path, sep="\t")

    required_cols = {"keyword_id", "keyword_name", "assigned_moods", "assignment_type"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in TSV: {missing}")

    log.info(
        "Loaded %d keywords: %d single, %d multi, %d none",
        len(df),
        (df["assignment_type"] == "single").sum(),
        (df["assignment_type"] == "multi").sum(),
        (df["assignment_type"] == "none").sum(),
    )
    return df


def get_single_label_subset(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Extract single-label keywords for classifier training."""
    single = df[df["assignment_type"] == "single"].copy()

    keywords = single["keyword_name"].tolist()
    labels = single["assigned_moods"].tolist()

    # Validate all labels are valid moods
    invalid = set(labels) - set(MOODS)
    if invalid:
        raise ValueError(f"Invalid mood labels found: {invalid}")

    log.info("Single-label subset: %d keywords, %d classes", len(keywords), len(set(labels)))
    for mood in MOODS:
        count = labels.count(mood)
        if count > 0:
            log.info("  %-12s %d", mood, count)

    return keywords, labels


def generate_embeddings(
    texts: list[str],
    model_name: str = "google/embeddinggemma-300m",
    batch_size: int = 128,
) -> np.ndarray:
    """Generate sentence embeddings via SentenceTransformer."""
    from sentence_transformers import SentenceTransformer

    log.info("Loading embedding model: %s", model_name)
    model = SentenceTransformer(model_name)

    log.info("Generating embeddings for %d texts (batch_size=%d)", len(texts), batch_size)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    log.info("Embedding shape: %s", embeddings.shape)
    return embeddings


def _evaluate(clf: object, x: np.ndarray, y: np.ndarray) -> dict:
    """Compute accuracy, precision, recall, F1 (macro) for a fitted classifier."""
    y_pred = clf.predict(x)
    return {
        "Accuracy": accuracy_score(y, y_pred),
        "Precision": precision_score(y, y_pred, average="macro", zero_division=0),
        "Recall": recall_score(y, y_pred, average="macro", zero_division=0),
        "F1 (macro)": f1_score(y, y_pred, average="macro", zero_division=0),
    }


def train_and_select(
    x_train: np.ndarray,
    x_val: np.ndarray,
    y_train: np.ndarray,
    y_val: np.ndarray,
    x_train_unscaled: np.ndarray,
    x_val_unscaled: np.ndarray,
    label_names: list[str],
) -> tuple[object, str, pd.DataFrame]:
    """Train classifiers (scaled + unscaled), select best by val F1. See CLASSIFICATION.md."""
    # Curse of dimensionality (lecture 11, slide 9): KNN is expected to
    # struggle with 768-dim embeddings because distance metrics lose
    # discriminative power in high-dimensional spaces. We include it for
    # course compliance but expect linear models to outperform.
    classifiers = {
        "KNN (k=5)": KNeighborsClassifier(n_neighbors=5),
        "SVC": SVC(gamma="scale", class_weight="balanced", probability=True),
        "GaussianNB": GaussianNB(),
        "LogisticRegression": LogisticRegression(
            max_iter=1000, class_weight="balanced",
        ),
        "MLPClassifier": MLPClassifier(
            hidden_layer_sizes=(128, 64), max_iter=500, random_state=42,
        ),
        "Dummy (most_frequent)": DummyClassifier(strategy="most_frequent"),
        "Dummy (stratified)": DummyClassifier(strategy="stratified", random_state=42),
    }

    results = []
    fitted_models = {}

    for name, clf in classifiers.items():
        log.info("Training %s ...", name)

        # --- Scaled variant ---
        clf.fit(x_train, y_train)
        train_metrics = _evaluate(clf, x_train, y_train)
        val_metrics = _evaluate(clf, x_val, y_val)
        results.append({
            "Classifier": name,
            "Scaling": "Scaled",
            "Train Acc": train_metrics["Accuracy"],
            "Train F1": train_metrics["F1 (macro)"],
            "Val Acc": val_metrics["Accuracy"],
            "Val Prec": val_metrics["Precision"],
            "Val Rec": val_metrics["Recall"],
            "Val F1": val_metrics["F1 (macro)"],
        })
        # Keep the scaled fitted model for selection
        fitted_models[name] = clf

        # --- Unscaled variant (fresh instance with same params) ---
        clf_unscaled = clf.__class__(**clf.get_params())
        clf_unscaled.fit(x_train_unscaled, y_train)
        train_metrics_u = _evaluate(clf_unscaled, x_train_unscaled, y_train)
        val_metrics_u = _evaluate(clf_unscaled, x_val_unscaled, y_val)
        results.append({
            "Classifier": name,
            "Scaling": "Unscaled",
            "Train Acc": train_metrics_u["Accuracy"],
            "Train F1": train_metrics_u["F1 (macro)"],
            "Val Acc": val_metrics_u["Accuracy"],
            "Val Prec": val_metrics_u["Precision"],
            "Val Rec": val_metrics_u["Recall"],
            "Val F1": val_metrics_u["F1 (macro)"],
        })

    results_df = pd.DataFrame(results)
    log.info(
        "\nClassifier comparison (train + val, scaled + unscaled):\n%s",
        results_df.to_string(index=False),
    )

    # Select best non-dummy classifier by Val F1 (scaled variant)
    scaled_non_dummy = results_df[
        (~results_df["Classifier"].str.startswith("Dummy"))
        & (results_df["Scaling"] == "Scaled")
    ]
    best_row = scaled_non_dummy.sort_values("Val F1", ascending=False).iloc[0]
    best_name = best_row["Classifier"]
    best_clf = fitted_models[best_name]
    best_f1 = best_row["Val F1"]

    # Overfitting check: compare train vs val F1
    train_f1 = best_row["Train F1"]
    gap = train_f1 - best_f1
    log.info(
        "Best classifier: %s (val F1=%.4f, train F1=%.4f, gap=%.4f)",
        best_name, best_f1, train_f1, gap,
    )
    if gap > 0.15:
        log.warning("Overfitting detected: train-val gap %.4f > 0.15", gap)

    return best_clf, best_name, results_df


def report_on_test_set(
    clf: object,
    clf_name: str,
    x_test: np.ndarray,
    y_test: np.ndarray,
    label_names: list[str],
    output_dir: Path,
) -> None:
    """Classification report + confusion matrix on held-out test set."""
    y_pred = clf.predict(x_test)

    # classification_report (lecture 11 slide 20, assignment 10 task 1.4)
    report = classification_report(y_test, y_pred, target_names=label_names)
    log.info(
        "\n=== Test Set Report: %s ===\n%s",
        clf_name, report,
    )

    # ConfusionMatrixDisplay (notebooks 10-0, 10-1, 10-2)
    fig, ax = plt.subplots(figsize=(8, 6))
    ConfusionMatrixDisplay.from_predictions(
        y_test, y_pred,
        display_labels=label_names,
        cmap="Blues",
        ax=ax,
    )
    ax.set_title(f"Confusion Matrix: {clf_name} (test set)")
    plt.tight_layout()

    plot_path = output_dir / "keyword_classifier_confusion_matrix.png"
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    log.info("Confusion matrix saved to %s", plot_path)


def load_all_keywords_from_db(db_path: Path) -> pd.DataFrame:
    """Load all keywords from tmdb.sqlite."""
    if not db_path.exists():
        raise FileNotFoundError(f"TMDB database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT id AS keyword_id, name AS keyword_name FROM keywords", conn)
    conn.close()

    log.info("Loaded %d keywords from tmdb.sqlite", len(df))
    return df


def build_keyword_mood_map(
    labeled_df: pd.DataFrame,
    unlabeled_keywords: list[str],
    unlabeled_predictions: np.ndarray,
    unlabeled_probas: np.ndarray | None,
    label_encoder: LabelEncoder,
) -> dict:
    """Build keyword→mood mapping: manual labels (single+multi) + classifier predictions."""
    mood_map = {}

    # Single-label keywords: use manual label with score 1.0
    single = labeled_df[labeled_df["assignment_type"] == "single"]
    for _, row in single.iterrows():
        mood = row["assigned_moods"]
        mood_map[row["keyword_name"]] = {mood.lower(): 1.0}

    # Multi-label keywords: split moods, assign equal weight
    multi = labeled_df[labeled_df["assignment_type"] == "multi"]
    for _, row in multi.iterrows():
        moods = [m.strip() for m in row["assigned_moods"].split(",")]
        weight = round(1.0 / len(moods), 2)
        mood_map[row["keyword_name"]] = {m.lower(): weight for m in moods}

    # "none" keywords are excluded (not mood-relevant)

    # Unlabeled keywords: use classifier predictions
    classes = label_encoder.classes_
    for i, keyword in enumerate(unlabeled_keywords):
        if unlabeled_probas is not None:
            # Use probability distribution across moods
            scores = {}
            for j, mood in enumerate(classes):
                prob = float(unlabeled_probas[i, j])
                if prob >= 0.05:
                    scores[mood.lower()] = round(prob, 3)
            if scores:
                mood_map[keyword] = scores
        else:
            # Binary prediction (no probabilities available)
            predicted_mood = classes[unlabeled_predictions[i]]
            mood_map[keyword] = {predicted_mood.lower(): 1.0}

    return mood_map


def main() -> int:
    """Run the keyword-to-mood classifier pipeline."""
    parser = argparse.ArgumentParser(
        description="Train keyword-to-mood classifier and infer labels for 70K+ keywords.",
    )
    parser.add_argument(
        "--tsv",
        type=Path,
        default=Path("data/source/labeled_keywords.tsv"),
        help="Path to labeled keyword TSV (default: data/source/labeled_keywords.tsv)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/source/tmdb.sqlite"),
        help="Path to TMDB SQLite database (default: data/source/tmdb.sqlite)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/models/keyword_mood_map.json"),
        help="Output path for keyword mood map JSON (default: data/models/keyword_mood_map.json)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="google/embeddinggemma-300m",
        help="Sentence-transformers model name (default: google/embeddinggemma-300m)",
    )
    parser.add_argument(
        "--eval-dir",
        type=Path,
        default=Path("docs"),
        help="Directory for evaluation outputs (default: docs/)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=128,
        help="Batch size for embedding generation (default: 128)",
    )
    args = parser.parse_args()

    # --- Step 1: Load and validate labeled data ---
    log.info("=== Step 1: Load labeled keywords ===")
    labeled_df = load_labeled_keywords(args.tsv)
    keywords, labels = get_single_label_subset(labeled_df)

    # --- Step 2: Generate embeddings for labeled keywords ---
    log.info("=== Step 2: Generate embeddings for labeled keywords ===")
    all_labeled_keywords = labeled_df["keyword_name"].tolist()
    all_labeled_embeddings = generate_embeddings(
        all_labeled_keywords, model_name=args.model, batch_size=args.batch_size,
    )

    # Extract single-label embeddings by index
    single_mask = labeled_df["assignment_type"] == "single"
    single_indices = single_mask[single_mask].index.tolist()
    x_single = all_labeled_embeddings[single_indices]

    # --- Step 3: 80/10/10 split — see CLASSIFICATION.md ---
    log.info("=== Step 3: 80/10/10 train/val/test split ===")
    le = LabelEncoder()
    y_encoded = le.fit_transform(labels)
    log.info("Label encoding: %s", dict(zip(le.classes_, le.transform(le.classes_))))

    x_trainval, x_test, y_trainval, y_test = train_test_split(
        x_single, y_encoded, test_size=0.10, stratify=y_encoded, random_state=13,
    )
    x_train, x_val, y_train, y_val = train_test_split(
        x_trainval, y_trainval, test_size=0.125, stratify=y_trainval, random_state=13,
    )
    log.info("Train: %d, Val: %d, Test: %d", len(x_train), len(x_val), len(x_test))

    # --- Step 4: Scaling (fit on train only) ---
    log.info("=== Step 4: RobustScaler (fit on train only) ===")
    scaler = RobustScaler()
    x_train_scaled = scaler.fit_transform(x_train)
    x_val_scaled = scaler.transform(x_val)
    x_test_scaled = scaler.transform(x_test)

    # --- Step 5: Train classifiers (scaled + unscaled, train + val) ---
    log.info("=== Step 5: Train classifiers (scaled + unscaled) ===")
    best_clf, best_name, results_df = train_and_select(
        x_train_scaled, x_val_scaled, y_train, y_val,
        x_train, x_val,  # unscaled
        le.classes_.tolist(),
    )

    # --- Step 6: Report on test set (used only once) ---
    log.info("=== Step 6: Report best classifier on test set ===")
    args.eval_dir.mkdir(parents=True, exist_ok=True)
    report_on_test_set(
        best_clf, best_name, x_test_scaled, y_test,
        le.classes_.tolist(), args.eval_dir,
    )

    # --- Step 7: Refit best model on full single-label set ---
    log.info("=== Step 7: Refit %s on full single-label set (%d) ===", best_name, len(x_single))
    scaler_full = RobustScaler()
    x_single_scaled = scaler_full.fit_transform(x_single)
    best_clf.fit(x_single_scaled, y_encoded)

    # --- Step 8: Load all keywords from tmdb.sqlite ---
    log.info("=== Step 8: Load keywords from tmdb.sqlite ===")
    all_keywords_df = load_all_keywords_from_db(args.db)

    # Identify unlabeled keywords (not in the 5,000 labeled set)
    labeled_names = set(labeled_df["keyword_name"].tolist())
    unlabeled_mask = ~all_keywords_df["keyword_name"].isin(labeled_names)
    unlabeled_df = all_keywords_df[unlabeled_mask]
    log.info("Unlabeled keywords to classify: %d", len(unlabeled_df))

    # --- Step 9: Generate embeddings for unlabeled keywords ---
    log.info("=== Step 9: Generate embeddings for unlabeled keywords ===")
    unlabeled_keywords = unlabeled_df["keyword_name"].tolist()
    unlabeled_embeddings = generate_embeddings(
        unlabeled_keywords, model_name=args.model, batch_size=args.batch_size,
    )

    # --- Step 10: Infer moods and export ---
    log.info("=== Step 10: Infer moods for unlabeled keywords ===")
    unlabeled_scaled = scaler_full.transform(unlabeled_embeddings)
    predictions = best_clf.predict(unlabeled_scaled)

    # Get probabilities if the classifier supports it
    probas = None
    if hasattr(best_clf, "predict_proba"):
        probas = best_clf.predict_proba(unlabeled_scaled)
        log.info("Using probability scores from %s", best_name)
    else:
        log.info("Using binary predictions (no predict_proba available)")

    mood_map = build_keyword_mood_map(
        labeled_df, unlabeled_keywords, predictions, probas, le,
    )

    # --- Step 11: Save output ---
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(mood_map, f, ensure_ascii=False, indent=None, separators=(",", ":"))

    file_size_mb = args.output.stat().st_size / (1024 * 1024)
    log.info("Saved %d keyword mood entries to %s (%.1f MB)", len(mood_map), args.output, file_size_mb)

    # Save results DataFrame for Phase 3 reuse
    results_path = args.eval_dir / "keyword_classifier_results.csv"
    results_df.to_csv(results_path, index=False)
    log.info("Classifier comparison saved to %s", results_path)

    # Summary
    log.info("=== Summary ===")
    log.info("Single-label (manual):  %d", (labeled_df["assignment_type"] == "single").sum())
    log.info("Multi-label (manual):   %d", (labeled_df["assignment_type"] == "multi").sum())
    log.info("Classified (inferred):  %d", len(unlabeled_keywords))
    log.info("Total in mood map:      %d", len(mood_map))
    log.info("Best classifier:        %s", best_name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
