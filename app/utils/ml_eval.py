"""Shared ML evaluation utility for the movie recommender.

Generic evaluation functions used by both the Statistics page (compact,
video-friendly) and the Jupyter notebook (academic, narrative). Works
on arbitrary (X, y) data — not tied to a specific classification task.

Two classification problems use these functions:
1. Keyword-to-mood: multi-class (7 moods), from Phase 1b
2. User preference: binary (liked/disliked), from Phase 2

Course foundation (all mandatory elements present):
    - train_test_split with stratify (Assignment 11 Task 1)
    - RobustScaler fit on train only (Assignment 11 Task 2)
    - 5+ classifier comparison as DataFrame (Assignment 11 Task 3.1)
    - Scaled vs unscaled comparison (Assignment 11 Task 3.1)
    - classification_report + ConfusionMatrixDisplay (Assignment 11 Task 3.2)
    - KFold cross-validation with mean +/- std (Notebook 10-1)
    - KNN hyperparameter tuning k=1..20 (Notebook 10-1)
    - DummyClassifier baselines (Notebook 10-2)
"""
from __future__ import annotations

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
from sklearn.model_selection import KFold, cross_val_score
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import RobustScaler
from sklearn.svm import SVC

# Non-interactive backend for saving plots without display
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def get_classifiers() -> dict[str, object]:
    """Return the standard set of classifiers for comparison.

    Includes 5 real classifiers + 2 DummyClassifier baselines.
    class_weight="balanced" where supported (handles class imbalance).

    Returns:
        Dict mapping classifier name to unfitted sklearn estimator.
    """
    return {
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
        "Dummy (stratified)": DummyClassifier(
            strategy="stratified", random_state=42,
        ),
    }


def evaluate_classifiers(
    x_train: np.ndarray,
    x_val: np.ndarray,
    y_train: np.ndarray,
    y_val: np.ndarray,
    scaled: bool = True,
) -> pd.DataFrame:
    """Train 5+ classifiers and evaluate on train + validation data.

    Follows Assignment 11 Task 3.1: evaluate on training AND validation
    data using accuracy, precision, recall, and F1 (macro).

    Args:
        x_train: Training features (scaled or unscaled).
        x_val: Validation features (scaled or unscaled).
        y_train: Training labels.
        y_val: Validation labels.
        scaled: Whether the input data is scaled (for labeling in DataFrame).

    Returns:
        DataFrame with columns: Classifier, Scaling, Train Acc, Train F1,
        Val Acc, Val Prec, Val Rec, Val F1. Sorted by Val F1 descending.
    """
    classifiers = get_classifiers()
    results = []

    for name, clf in classifiers.items():
        clf.fit(x_train, y_train)

        # Train metrics (overfitting check, lecture 11 slide 34)
        y_train_pred = clf.predict(x_train)
        train_acc = accuracy_score(y_train, y_train_pred)
        train_f1 = f1_score(y_train, y_train_pred, average="macro", zero_division=0)

        # Validation metrics
        y_val_pred = clf.predict(x_val)
        val_acc = accuracy_score(y_val, y_val_pred)
        val_prec = precision_score(y_val, y_val_pred, average="macro", zero_division=0)
        val_rec = recall_score(y_val, y_val_pred, average="macro", zero_division=0)
        val_f1 = f1_score(y_val, y_val_pred, average="macro", zero_division=0)

        results.append({
            "Classifier": name,
            "Scaling": "Scaled" if scaled else "Unscaled",
            "Train Acc": round(train_acc, 4),
            "Train F1": round(train_f1, 4),
            "Val Acc": round(val_acc, 4),
            "Val Prec": round(val_prec, 4),
            "Val Rec": round(val_rec, 4),
            "Val F1": round(val_f1, 4),
        })

    return pd.DataFrame(results).sort_values("Val F1", ascending=False)


def best_model_report(
    clf: object,
    x_test: np.ndarray,
    y_test: np.ndarray,
    label_names: list[str],
) -> tuple[str, plt.Figure]:
    """Generate classification report and confusion matrix for best model.

    Follows Assignment 11 Task 3.2: report performance on held-out test set.
    The test set is only used here, never during training or model selection.

    Args:
        clf: Fitted best classifier.
        x_test: Scaled test features.
        y_test: True test labels (encoded).
        label_names: Class names for display.

    Returns:
        Tuple of (classification_report string, confusion matrix figure).
    """
    y_pred = clf.predict(x_test)

    # classification_report (lecture 11 slide 20, assignment 10 task 1.4)
    report = classification_report(y_test, y_pred, target_names=label_names)

    # ConfusionMatrixDisplay (notebooks 10-0, 10-1, 10-2)
    fig, ax = plt.subplots(figsize=(8, 6))
    ConfusionMatrixDisplay.from_predictions(
        y_test, y_pred,
        display_labels=label_names,
        cmap="Blues",
        ax=ax,
    )
    ax.set_title("Confusion Matrix (test set)")
    plt.tight_layout()

    return report, fig


def run_cross_validation(
    clf: object,
    x: np.ndarray,
    y: np.ndarray,
    n_splits: int = 10,
) -> np.ndarray:
    """Run K-Fold cross-validation and return scores.

    Follows Notebook 10-1: KFold with shuffle, report mean +/- std accuracy.

    Args:
        clf: Unfitted sklearn estimator (will be cloned internally by
            cross_val_score).
        x: Full feature matrix (all data, not just train).
        y: Full label vector.
        n_splits: Number of folds (default: 10).

    Returns:
        Array of accuracy scores per fold.
    """
    kfold = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    scores = cross_val_score(clf, x, y, cv=kfold, scoring="accuracy")
    return scores


def knn_hyperparameter_plot(
    x_train: np.ndarray,
    x_val: np.ndarray,
    y_train: np.ndarray,
    y_val: np.ndarray,
    k_range: range | None = None,
) -> plt.Figure:
    """Plot KNN accuracy vs k for hyperparameter tuning.

    Follows Notebook 10-1: vary k from 1 to 20, plot accuracy on
    train and validation sets to detect overfitting.

    Args:
        x_train: Scaled training features.
        x_val: Scaled validation features.
        y_train: Training labels.
        y_val: Validation labels.
        k_range: Range of k values to test (default: 1..20).

    Returns:
        Matplotlib figure with train and validation accuracy curves.
    """
    if k_range is None:
        k_range = range(1, 21)

    train_scores = []
    val_scores = []

    for k in k_range:
        knn = KNeighborsClassifier(n_neighbors=k)
        knn.fit(x_train, y_train)
        train_scores.append(accuracy_score(y_train, knn.predict(x_train)))
        val_scores.append(accuracy_score(y_val, knn.predict(x_val)))

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(list(k_range), train_scores, "o-", label="Train accuracy")
    ax.plot(list(k_range), val_scores, "o-", label="Validation accuracy")
    ax.set_xlabel("k (number of neighbors)")
    ax.set_ylabel("Accuracy")
    ax.set_title("KNN Hyperparameter Tuning")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xticks(list(k_range))
    plt.tight_layout()

    return fig
