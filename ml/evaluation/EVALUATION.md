# EVALUATION

Academic ML evaluation: shared utility functions and Jupyter notebook.

---

## Two Classification Tasks

1. **User preference:** Binary — predict "liked" (>= 60/100) vs "disliked" (< 60/100) from 9 scoring-component feature vectors
2. **Keyword-to-mood:** Multi-class — predict mood category from sentence embeddings of TMDB keywords (70K+ keywords, 7 moods)

Both follow the same course-compliant evaluation workflow.

---

## Mandatory Elements (course baseline)

1. Stratified train/test split with fixed random_state
2. Data scaling (RobustScaler, fit on train only)
3. 5+ classifier comparison (KNN, SVC, GaussianNB, LogisticRegression, MLPClassifier) + DummyClassifier baselines
4. Metrics DataFrame: accuracy, precision, recall, F1 (macro)
5. Confusion matrix + classification_report for best model
6. 10-fold cross-validation with mean +/- std
7. Scaled vs. unscaled comparison
8. KNN hyperparameter tuning (k=1..20 plot)

---

## Beyond Course (for score 3)

- TF-IDF + TruncatedSVD on 1.17M movies
- Content-based scoring with 9 weighted signals
- Pre-trained emotion transformer
- Dynamic weight shifting by rating count
- Supervised keyword-to-mood pipeline (embeddings + classifier)

---

## Shared Utility

`ml_eval.py` contains all evaluation logic. Called by both the Statistics page (compact, video-friendly) and `ml_evaluation.ipynb` (academic, narrative). No duplicated code.
