"""Academic ML evaluation: classifier comparison, cross-validation, plots."""
from ml.evaluation.ml_eval import (
    best_model_report,
    evaluate_classifiers,
    get_classifiers,
    knn_hyperparameter_plot,
    run_cross_validation,
)

__all__ = [
    "best_model_report",
    "evaluate_classifiers",
    "get_classifiers",
    "knn_hyperparameter_plot",
    "run_cross_validation",
]
