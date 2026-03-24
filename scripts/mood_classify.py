#!/usr/bin/env python3
"""Mood classification pipeline for TMDB keywords.

Two-phase pipeline that assigns ~34k TMDB keywords to 10 mood categories:

Phase 1 (Labeling — NOT ML):
    Embeds all keywords using Google EmbeddingGemma-300M via sentence-transformers
    with Matryoshka truncation to 256 dimensions. Computes mood centroids from
    hand-curated seed keywords, then assigns each keyword to the nearest centroid
    via cosine similarity (above a configurable threshold).

Phase 2 (ML — demonstrable classifier):
    Trains a scikit-learn classifier on the Phase 1 labels with train/test split.
    Evaluates via accuracy and weighted F1-score. Predicts mood labels for
    previously unlabeled keywords that exceed a lower confidence threshold.

Output:
    keyword_moods table in keywords.db with columns:
    keyword_id, mood_category, similarity, source (labeling|classifier)

Course: Grundlagen und Methoden der Informatik, FS26
University: University of St. Gallen (HSG)

AI Citation: Core pipeline structure and embedding integration written with
Claude Code (Anthropic). Seed keywords hand-curated by team.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import normalize


def load_keywords(db_path: Path) -> list[dict]:
    """Load unique keywords from keywords.db.

    Args:
        db_path: Path to the keywords SQLite database.

    Returns:
        List of dicts with keyword_id and keyword_name.
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT DISTINCT keyword_id, keyword_name FROM movie_keywords"
    ).fetchall()
    conn.close()
    return [{"keyword_id": r["keyword_id"], "keyword_name": r["keyword_name"]} for r in rows]


def load_seed_keywords(seed_path: Path) -> dict[str, list[str]]:
    """Load hand-curated seed keywords from JSON.

    Supports two formats:
    - Simple: {"mood": ["word1", "word2"]}
    - Rich:   {"mood": [{"id": 1, "name": "word1", "frequency": 100}, ...]}

    Args:
        seed_path: Path to the seed keywords JSON file.

    Returns:
        Dict mapping mood category name to list of seed keyword name strings.
    """
    raw = json.loads(seed_path.read_text())
    result: dict[str, list[str]] = {}
    for mood, seeds in raw.items():
        if seeds and isinstance(seeds[0], dict):
            result[mood] = [s["name"] for s in seeds]
        else:
            result[mood] = seeds
    return result


def embed_keywords(
    model: SentenceTransformer,
    texts: list[str],
    batch_size: int = 256,
) -> np.ndarray:
    """Embed keyword texts using the sentence-transformers model.

    Args:
        model: Loaded SentenceTransformer model.
        texts: List of keyword name strings to embed.
        batch_size: Batch size for encoding.

    Returns:
        L2-normalized embedding matrix of shape (len(texts), truncate_dim).
    """
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    return embeddings


def compute_centroids(
    model: SentenceTransformer,
    seed_keywords: dict[str, list[str]],
) -> tuple[list[str], np.ndarray]:
    """Compute mood centroids from seed keyword embeddings.

    For each mood category, embeds its seed keywords and averages the vectors
    to produce a single centroid. Centroids are L2-normalized.

    Args:
        model: Loaded SentenceTransformer model.
        seed_keywords: Dict mapping mood name to list of seed keyword strings.

    Returns:
        Tuple of (mood_names list, centroids matrix of shape (n_moods, dim)).
    """
    mood_names = list(seed_keywords.keys())
    centroids = []
    for mood in mood_names:
        seeds = seed_keywords[mood]
        seed_embeddings = model.encode(seeds, normalize_embeddings=True)
        # Average seed vectors to get the mood centroid
        centroid = seed_embeddings.mean(axis=0)
        centroids.append(centroid)
    centroid_matrix = np.array(centroids)
    # L2-normalize centroids so dot product = cosine similarity
    centroid_matrix = normalize(centroid_matrix)
    return mood_names, centroid_matrix


def phase1_labeling(
    keyword_embeddings: np.ndarray,
    keywords: list[dict],
    mood_names: list[str],
    centroids: np.ndarray,
    threshold: float,
) -> tuple[list[dict], list[dict]]:
    """Phase 1: Assign keywords to moods via cosine similarity to centroids.

    This is semi-automatic labeling, NOT machine learning. Each keyword is
    assigned to the mood whose centroid is closest, provided the similarity
    exceeds the threshold.

    Args:
        keyword_embeddings: Normalized embedding matrix (n_keywords, dim).
        keywords: List of keyword dicts with keyword_id and keyword_name.
        mood_names: Ordered list of mood category names.
        centroids: Normalized centroid matrix (n_moods, dim).
        threshold: Minimum cosine similarity to assign a label.

    Returns:
        Tuple of (labeled list, unlabeled list). Each labeled entry has
        keyword_id, keyword_name, mood_category, similarity.
    """
    # Cosine similarity: dot product of normalized vectors
    # Shape: (n_keywords, n_moods)
    similarities = keyword_embeddings @ centroids.T

    labeled = []
    unlabeled = []
    for i, kw in enumerate(keywords):
        best_mood_idx = int(similarities[i].argmax())
        best_sim = float(similarities[i, best_mood_idx])
        if best_sim >= threshold:
            labeled.append({
                "keyword_id": kw["keyword_id"],
                "keyword_name": kw["keyword_name"],
                "mood_category": mood_names[best_mood_idx],
                "similarity": round(best_sim, 4),
            })
        else:
            unlabeled.append({
                "keyword_id": kw["keyword_id"],
                "keyword_name": kw["keyword_name"],
                "best_similarity": round(best_sim, 4),
            })

    return labeled, unlabeled


def phase2_classifier(
    keyword_embeddings: np.ndarray,
    keywords: list[dict],
    labeled: list[dict],
    unlabeled: list[dict],
    mood_names: list[str],
    test_size: float = 0.2,
    n_neighbors: int = 7,
    classifier_threshold: float = 0.5,
) -> tuple[list[dict], dict]:
    """Phase 2: Train a KNN classifier on Phase 1 labels and predict unlabeled.

    This is the demonstrable ML step: train/test split, model training,
    evaluation via accuracy and F1-score, then prediction on unlabeled keywords.

    Args:
        keyword_embeddings: Full embedding matrix (n_keywords, dim).
        keywords: Full keyword list (same order as embeddings).
        labeled: Labeled keywords from Phase 1.
        unlabeled: Unlabeled keywords from Phase 1.
        mood_names: Ordered list of mood category names.
        test_size: Fraction of labeled data for testing.
        n_neighbors: Number of neighbors for KNN.
        classifier_threshold: Min prediction probability to accept a label.

    Returns:
        Tuple of (newly_labeled list, metrics dict with accuracy, f1, report).
    """
    # Build keyword_id -> index mapping for embedding lookup
    id_to_idx = {kw["keyword_id"]: i for i, kw in enumerate(keywords)}

    # Prepare training data from Phase 1 labels
    labeled_ids = [entry["keyword_id"] for entry in labeled]
    labeled_indices = [id_to_idx[kid] for kid in labeled_ids]
    X_labeled = keyword_embeddings[labeled_indices]
    y_labeled = np.array([entry["mood_category"] for entry in labeled])

    # Train/test split (stratified to preserve class balance)
    X_train, X_test, y_train, y_test = train_test_split(
        X_labeled, y_labeled,
        test_size=test_size,
        random_state=42,
        stratify=y_labeled,
    )

    print(f"\n{'='*60}")
    print("PHASE 2: Machine Learning Classifier")
    print(f"{'='*60}")
    print(f"Training samples: {len(X_train)}")
    print(f"Test samples:     {len(X_test)}")
    print(f"Classes:          {len(mood_names)}")
    print(f"Classifier:       KNeighborsClassifier(n_neighbors={n_neighbors})")

    # Train KNN classifier
    clf = KNeighborsClassifier(n_neighbors=n_neighbors, metric="cosine")
    clf.fit(X_train, y_train)

    # Evaluate on test set
    y_pred = clf.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average="weighted")
    report = classification_report(y_test, y_pred, zero_division=0)

    print(f"\nAccuracy:     {accuracy:.4f}")
    print(f"F1 (weighted): {f1:.4f}")
    print(f"\nClassification Report:\n{report}")

    # Re-train on ALL labeled data for final predictions
    clf_final = KNeighborsClassifier(n_neighbors=n_neighbors, metric="cosine")
    clf_final.fit(X_labeled, y_labeled)

    # Predict unlabeled keywords with probability threshold
    newly_labeled = []
    if unlabeled:
        unlabeled_ids = [entry["keyword_id"] for entry in unlabeled]
        unlabeled_indices = [id_to_idx[kid] for kid in unlabeled_ids]
        X_unlabeled = keyword_embeddings[unlabeled_indices]

        predictions = clf_final.predict(X_unlabeled)
        probabilities = clf_final.predict_proba(X_unlabeled)

        for i, entry in enumerate(unlabeled):
            max_prob = float(probabilities[i].max())
            if max_prob >= classifier_threshold:
                newly_labeled.append({
                    "keyword_id": entry["keyword_id"],
                    "keyword_name": entry["keyword_name"],
                    "mood_category": predictions[i],
                    "similarity": round(max_prob, 4),
                })

        print(f"\nUnlabeled keywords:  {len(unlabeled)}")
        print(f"Newly classified:    {len(newly_labeled)} (threshold >= {classifier_threshold})")
        print(f"Still unlabeled:     {len(unlabeled) - len(newly_labeled)}")

    metrics = {
        "accuracy": round(accuracy, 4),
        "f1_weighted": round(f1, 4),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "n_neighbors": n_neighbors,
        "report": report,
    }
    return newly_labeled, metrics


def write_to_db(
    db_path: Path,
    labeled: list[dict],
    classifier_labeled: list[dict],
) -> None:
    """Write mood assignments to the keyword_moods table in keywords.db.

    Creates the table if it doesn't exist. Clears previous results before
    writing (idempotent).

    Args:
        db_path: Path to the keywords SQLite database.
        labeled: Phase 1 labeled keywords.
        classifier_labeled: Phase 2 classifier-predicted keywords.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS keyword_moods (
            keyword_id     INTEGER PRIMARY KEY,
            mood_category  TEXT NOT NULL,
            similarity     REAL NOT NULL,
            source         TEXT NOT NULL CHECK (source IN ('labeling', 'classifier'))
        )
    """)
    # Clear previous results for idempotent re-runs
    conn.execute("DELETE FROM keyword_moods")

    # Insert Phase 1 labels
    for entry in labeled:
        conn.execute(
            "INSERT INTO keyword_moods (keyword_id, mood_category, similarity, source) "
            "VALUES (?, ?, ?, 'labeling')",
            (entry["keyword_id"], entry["mood_category"], entry["similarity"]),
        )

    # Insert Phase 2 classifier predictions
    for entry in classifier_labeled:
        conn.execute(
            "INSERT OR IGNORE INTO keyword_moods (keyword_id, mood_category, similarity, source) "
            "VALUES (?, ?, ?, 'classifier')",
            (entry["keyword_id"], entry["mood_category"], entry["similarity"]),
        )

    conn.commit()

    # Summary
    total = conn.execute("SELECT COUNT(*) FROM keyword_moods").fetchone()[0]
    by_source = conn.execute(
        "SELECT source, COUNT(*) FROM keyword_moods GROUP BY source"
    ).fetchall()
    by_mood = conn.execute(
        "SELECT mood_category, COUNT(*) FROM keyword_moods GROUP BY mood_category ORDER BY COUNT(*) DESC"
    ).fetchall()
    conn.close()

    print(f"\n{'='*60}")
    print("OUTPUT: keyword_moods table in keywords.db")
    print(f"{'='*60}")
    print(f"Total assigned: {total}")
    for source, count in by_source:
        print(f"  {source}: {count}")
    print(f"\nPer mood category:")
    for mood, count in by_mood:
        print(f"  {count:>5}x  {mood}")


def main() -> None:
    """Run the two-phase mood classification pipeline."""
    parser = argparse.ArgumentParser(
        description="Classify TMDB keywords into mood categories using "
        "EmbeddingGemma-300M embeddings and KNN.",
    )
    parser.add_argument(
        "--db", type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "keywords.db",
        help="Path to keywords.db (default: data/keywords.db)",
    )
    parser.add_argument(
        "--seeds", type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "seed_keywords.json",
        help="Path to seed keywords JSON (default: data/seed_keywords.json)",
    )
    parser.add_argument(
        "--model", type=str,
        default="google/embeddinggemma-300m",
        help="Sentence-transformers model name (default: google/embeddinggemma-300m)",
    )
    parser.add_argument(
        "--dim", type=int, default=256,
        help="Matryoshka truncation dimension (default: 256)",
    )
    parser.add_argument(
        "--threshold", type=float, default=0.4,
        help="Cosine similarity threshold for Phase 1 labeling (default: 0.4)",
    )
    parser.add_argument(
        "--classifier-threshold", type=float, default=0.5,
        help="Prediction probability threshold for Phase 2 classifier (default: 0.5)",
    )
    parser.add_argument(
        "--n-neighbors", type=int, default=7,
        help="Number of neighbors for KNN classifier (default: 7)",
    )
    parser.add_argument(
        "--test-size", type=float, default=0.2,
        help="Fraction of labeled data for test set (default: 0.2)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run pipeline without writing to database",
    )
    args = parser.parse_args()

    # Validate inputs
    if not args.db.exists():
        print(f"Error: Database not found: {args.db}", file=sys.stderr)
        sys.exit(1)
    if not args.seeds.exists():
        print(f"Error: Seed keywords not found: {args.seeds}", file=sys.stderr)
        sys.exit(1)

    t_start = time.time()

    # --- Load data ---
    print(f"Loading keywords from {args.db}")
    keywords = load_keywords(args.db)
    print(f"  {len(keywords)} unique keywords")

    print(f"Loading seed keywords from {args.seeds}")
    seed_keywords = load_seed_keywords(args.seeds)
    n_seeds = sum(len(v) for v in seed_keywords.values())
    print(f"  {len(seed_keywords)} mood categories, {n_seeds} seed keywords total")

    # --- Load model ---
    print(f"\nLoading model: {args.model}")
    print(f"  Matryoshka truncation: {args.dim} dimensions")
    model = SentenceTransformer(args.model, truncate_dim=args.dim)

    # --- Embed all keywords ---
    print(f"\nEmbedding {len(keywords)} keywords...")
    keyword_texts = [kw["keyword_name"] for kw in keywords]
    keyword_embeddings = embed_keywords(model, keyword_texts)
    print(f"  Embedding shape: {keyword_embeddings.shape}")

    # --- Phase 1: Centroid-based labeling ---
    print(f"\n{'='*60}")
    print("PHASE 1: Semi-automatic Labeling (NOT ML)")
    print(f"{'='*60}")
    print(f"Computing mood centroids from seed keywords...")
    mood_names, centroids = compute_centroids(model, seed_keywords)
    print(f"  Centroid shape: {centroids.shape}")

    print(f"Assigning keywords to moods (threshold >= {args.threshold})...")
    labeled, unlabeled = phase1_labeling(
        keyword_embeddings, keywords, mood_names, centroids, args.threshold,
    )
    print(f"  Labeled:   {len(labeled)}")
    print(f"  Unlabeled: {len(unlabeled)}")

    # Per-mood breakdown
    from collections import Counter
    mood_counts = Counter(entry["mood_category"] for entry in labeled)
    print(f"\n  Per mood category (Phase 1):")
    for mood in mood_names:
        print(f"    {mood_counts.get(mood, 0):>5}x  {mood}")

    # --- Phase 2: Classifier ---
    classifier_labeled, metrics = phase2_classifier(
        keyword_embeddings, keywords, labeled, unlabeled, mood_names,
        test_size=args.test_size,
        n_neighbors=args.n_neighbors,
        classifier_threshold=args.classifier_threshold,
    )

    # --- Write results ---
    if args.dry_run:
        print(f"\n[DRY RUN] Would write {len(labeled) + len(classifier_labeled)} "
              f"entries to keyword_moods table")
    else:
        write_to_db(args.db, labeled, classifier_labeled)

    elapsed = time.time() - t_start
    print(f"\nPipeline completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
