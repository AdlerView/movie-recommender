# EVALUATION

Academic ML evaluation: shared utility functions (`ml_eval.py`) and Jupyter notebook (`ml_evaluation.ipynb`).

---

## Two Classification Tasks

1. **User preference:** Binary — predict "liked" (>= 60/100) vs "disliked" (< 60/100) from 9 scoring-component feature vectors
2. **Keyword-to-mood:** Multi-class — predict mood category from sentence embeddings of TMDB keywords (70K+ keywords, 7 moods)

Both follow the same course-compliant evaluation workflow.

---

## Course Expectations (Requirement 5: Machine Learning)

The course (4,125 Grundlagen und Methoden der Informatik, FS26) teaches ML
via scikit-learn in weeks 10-11. To score 3 ("outstanding, far beyond the
level of this course"), the project must demonstrate mastery of everything
taught AND go beyond it.

---

### Mandatory Elements (course baseline)

From lectures 10/11, notebooks 10-0 through 11, and assignments 10-11:

1. **Train/test split** — `train_test_split(stratify=..., random_state=...)`
2. **Data scaling** — `RobustScaler` (fit on train, transform train+test)
3. **5+ classifier comparison:**

   | Classifier | sklearn Class | Key Params |
   |---|---|---|
   | KNN | `KNeighborsClassifier` | `n_neighbors=5` |
   | SVM | `SVC` | `gamma="scale"` |
   | Naive Bayes | `GaussianNB` | — |
   | Logistic Regression | `LogisticRegression` | `max_iter=1000` |
   | Neural Network | `MLPClassifier` | `hidden_layer_sizes=[64, 64]` |
   | Baseline (frequent) | `DummyClassifier` | `strategy="most_frequent"` |
   | Baseline (stratified) | `DummyClassifier` | `strategy="stratified"` |

4. **Metrics per classifier (DataFrame)** — accuracy, precision (macro), recall (macro), F1 (macro). Compare scaled vs unscaled.
5. **Best model deep dive** — `ConfusionMatrixDisplay.from_predictions`, `classification_report`
6. **Cross-validation** — `KFold(n_splits=10, shuffle=True, random_state=42)` + `cross_val_score`, report mean ± std
7. **Hyperparameter tuning** — at least vary k in KNN (1-20), plot accuracy vs k

---

### Beyond Course (for score 3)

- TF-IDF + TruncatedSVD on 1.17M movies (SVD dimensionality reduction not taught)
- Content-based scoring with 9 weighted signals
- Pre-trained emotion transformer (distilroberta)
- Dynamic weight shifting by rating count (cold start handling)
- Supervised keyword-to-mood pipeline (embeddings + classifier)
- Bayesian average quality scoring

---

## Evaluation Workflow

---

### User Preference Classification

- **Features (X):** For each (user, movie) pair, the 9 scoring components:
  `[keyword_sim, mood_match, director_sim, actor_sim, decade_sim,
   language_sim, runtime_sim, quality_score, contra_penalty]`
- **Labels (y):** Binary — `1` = liked (>= 60/100), `0` = disliked (< 60/100)
- **Data source:** All entries in `user_ratings` table

```python
# 1. Data preparation
X, y = build_features_and_labels(user_ratings, model_arrays)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

# 2. Scaling
scaler = RobustScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# 3. Classifier comparison (DataFrame of results)
estimators = {
    "KNN": KNeighborsClassifier(n_neighbors=5),
    "SVC": SVC(gamma="scale"),
    "GaussianNB": GaussianNB(),
    "LogisticRegression": LogisticRegression(max_iter=1000),
    "MLPClassifier": MLPClassifier(hidden_layer_sizes=[64, 64]),
    "DummyClassifier": DummyClassifier(strategy="most_frequent"),
}

# 4. Best model: confusion matrix + classification_report
# 5. Cross-validation: KFold(n_splits=10) + cross_val_score
```

---

### Keyword-to-Mood Classification

Uses the single-label subset (1,049 keywords) with EmbeddingGemma-300M
sentence embeddings (768-dim). Same workflow as above. See
`ml/classification/CLASSIFICATION.md` for full labeling pipeline and
class distribution details.

---

## Where to Show

Both locations, with shared logic:

- **Statistics page** (compact, video-friendly): classifier comparison table, best model KPIs (accuracy + F1), confusion matrix, classification report, cross-validation score
- **Jupyter notebook** `ml_evaluation.ipynb` (academic, narrative): problem definition, feature engineering explanation, data distribution plots, all 7 classifiers with commentary, scaled vs unscaled comparison, KNN hyperparameter tuning (k=1..20 plot), discussion/interpretation

Separation principle: notebook shows the "why", Statistics page shows
the result. No duplicated code — both call `ml_eval.py`.

---

## Shared Utility

`ml_eval.py` contains all evaluation logic:
- `evaluate_classifiers()` — run all classifiers, return metrics DataFrame
- `best_model_report()` — confusion matrix + classification report for best model
- `run_cross_validation()` — KFold cross-validation with mean ± std
- `knn_hyperparameter_plot()` — accuracy vs k plot

---

## Cold Start Handling

With 0 ratings, the classifier cannot run. Scoring falls back to:
- Quality score (Bayesian average) + mood match (if selected)
- No personalization signals until >= 1 rating
- Dynamic weight table shifts from quality-heavy to personalization-heavy as ratings accumulate (see `ml/scoring/SCORING.md`)
