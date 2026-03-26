# DECISIONS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Created:** 2026-03-25
**Updated:** 2026-03-26

---

## [25-03-25] Dismiss signal as negative input for scoring

**Type:** architecture
**Status:** decided

### Context
Open Issue #010: The wireframe has a "not interested" button. It was
unclear whether dismissals should feed into the ML model as negative
training signals or just be cosmetically filtered out.

### Decision
Dismissals are negative signals in Layer 2 (online scoring). They
contribute to the contra vector alongside low-rated movies. Exact
weight is TBD during `scoring.py` implementation. They are NOT used
in the offline pipeline (Layer 1). Implementation deferred to Phase 2
(online scoring); during Phase 0 (DB migration + UI), dismissals
remain cosmetic only.

### Alternatives Considered
- Cosmetic only (simpler, but loses useful signal)
- Immediate implementation (rejected -- Phase 0 should not depend on
  scoring.py)

### Consequences
- `scoring.py` must query the `dismissed` table when building the
  contra vector
- Contra vector weight for dismissed movies needs tuning (separate
  from low-rating weight)

---

## [25-03-25] "Based on your interests" poster grid on Rate page

**Type:** architecture
**Status:** decided

### Context
Open Issue #011: The wireframe showed a "based on your stream" section
with poster thumbnails. No streaming integration exists. The section
needed a concrete definition.

### Decision
"Based on your interests" section on the Rate page, displayed as a
poster grid identical to the existing trending movies layout. Powered
by the personalized scoring system (Layer 2). Shows top-N recommended
movies from the user's rating history. Falls back to trending when no
ratings exist or model/ directory is not populated.

### Alternatives Considered
- Drop the section entirely (rejected -- it showcases the ML scoring
  system and matches the wireframe)
- Show recently rated movies (rejected -- already visible on
  Statistics page, no added value)

### Consequences
- Rate page gains a second poster grid section below trending
- Requires model/ directory + scoring.py to be functional for
  personalized results
- Graceful fallback to trending needed for cold start

---

## [25-03-25] Keyword-to-mood mapping via supervised pipeline

**Type:** architecture | data-model
**Status:** decided

### Context
TMDB has 70K+ unique keywords. The original plan called for manual
tagging of the top-500 keywords. This was infeasible and
methodologically weak.

### Decision
Two-stage supervised pipeline:

**Stage A (complete):** 5,000 keywords labeled by Claude agent in
`data/tmdb-keyword-frequencies_labeled_top5000.tsv` (1,697 single,
2,047 multi, 1,256 none).

**Stage B:** Course-compliant supervised classification:
1. EmbeddingGemma-300M sentence embeddings (256-dim) as features
2. Single-label subset only (1,697 keywords) for training
3. Stratified train/test split
4. RobustScaler on embeddings
5. 5+ classifier comparison (KNN, SVC, GaussianNB, LogisticRegression,
   MLPClassifier) + DummyClassifier baselines
6. Full evaluation (classification_report, confusion matrix, CV)
7. Best model infers mood labels for all remaining 70K+ keywords

This serves as a second ML showcase alongside user preference
classification.

### Alternatives Considered
- Manual tagging of top-500 (infeasible at scale, not reproducible)
- Zero-shot classifier alone (fragile for short keyword phrases)
- Claude API batch tagging (expensive, less reproducible)
- NRC Emotion Lexicon (poor fit for film keyword taxonomy)
- Sentence embeddings + seed words only (less scientifically
  convincing than supervised pipeline)

### Consequences
- New file: `pipeline/keyword_mood_classifier.py`
- `model/keyword_mood_map.json` grows from ~500 to ~70K entries
- Two classification problems in the ML evaluation (user preference +
  keyword-to-mood)
- Requires sentence-transformers package in conda environment
- Labeled seed dataset must be created before pipeline can run

---

## [25-03-25] ML evaluation in both Statistics page and Jupyter notebook

**Type:** architecture
**Status:** decided

### Context
The course requires ML evaluation (Requirement 5). The question was
whether to show it in the running app, a notebook, or both.

### Decision
Both, with shared logic and no code duplication:

- **Shared utility:** `app/utils/ml_eval.py`
  - `evaluate_classifiers(X, y, random_state=42) -> pd.DataFrame`
  - `best_model_report(X, y, clf) -> tuple[fig, str, ndarray]`
  - `run_cross_validation(clf, X, y, n_splits=10) -> ndarray`

- **Statistics page** (compact, video-friendly):
  - "Run ML Evaluation" button (cached)
  - Classifier comparison table
  - Best model: accuracy + F1 as st.metric KPIs
  - Confusion matrix plot
  - Classification report as table
  - Cross-validation score with delta to baseline

- **Jupyter notebook** (`notebooks/ml_evaluation.ipynb`):
  - Problem definition + feature engineering explanation
  - Data distribution plots
  - All 7 classifiers with commentary
  - Scaled vs unscaled comparison
  - KNN hyperparameter tuning (k=1..20 plot)
  - Discussion / interpretation

Separation principle: notebook shows the "why", Statistics page shows
the result. No duplicated code -- both call `ml_eval.py`.

### Alternatives Considered
- Statistics page only (not detailed enough for academic evaluation)
- Notebook only (not visible during video demo)

### Consequences
- New files: `app/utils/ml_eval.py`, `notebooks/ml_evaluation.ipynb`
- Statistics page gains an "ML Evaluation" section with a run button
- Notebook must be included in the final submission

---

## [26-03-26] Contra vector threshold: below 40/100

**Type:** architecture
**Status:** decided

### Context
The contra penalty signal needs a threshold to determine which rated
movies contribute to the "dislike" profile. The threshold affects how
aggressively the system penalizes thematically similar movies.

### Decision
Ratings below 40/100 (i.e., 0-30 on the step-of-10 scale) contribute
to the contra vector. This matches the "Poor" sentiment label range.

### Alternatives Considered
- Below 60/100 (same as liked/disliked boundary -- too aggressive,
  includes lukewarm "Decent" ratings)
- Tunable parameter (deferred complexity)

### Consequences
- `scoring.py` filters `user_ratings WHERE rating < 40` for contra
- Clear semantic boundary: only genuinely disliked movies feed the
  penalty signal

---

## [26-03-26] Keyword classifier uses single-label subset only

**Type:** architecture
**Status:** decided

### Context
The labeled keyword dataset has 1,697 single-label and 2,047
multi-label entries. Multi-label keywords could provide more training
data but complicate the classification pipeline.

### Decision
Train on single-label subset only (1,697 keywords, 7 classes). This
gives a methodologically clean multi-class classification problem that
maps directly to the course pipeline (train_test_split, classifier
comparison, confusion matrix).

Multi-label and none-labeled keywords are excluded from training but
retained in the dataset for reference.

### Alternatives Considered
- Multi-label from start with one-vs-rest (more data, but less clean
  for course compliance and harder to evaluate with standard metrics)
- Both approaches compared in notebook (added complexity for marginal
  benefit)

### Consequences
- 1,697 training samples across 7 classes
- Class imbalance exists (Interested: 910, Surprised: 17) -- must
  use stratified splits and report macro-F1 carefully
- `class_weight='balanced'` should be used where supported
