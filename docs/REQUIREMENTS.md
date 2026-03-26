# Requirements

> Grading criteria extracted from the course briefing.
> Each requirement is scored 0–3 points. The project accounts for 20% of the final grade.
> Source: [group-project.pdf](references/group-project.pdf)

---

## Scoring

| Points | Description |
|--------|-------------|
| 0      | Requirement not met / feature does not exist |
| 1      | Basic implementation, formally present but not very relevant to the problem |
| 2      | Good implementation |
| 3      | Outstanding implementation, far beyond the level of this course |

---

## Requirements

### 1. Problem Statement

> A problem that is solved by the application is clearly stated (e.g., business or consumer use case).

**Our approach:** With access to thousands of movies across all streaming platforms, it is easy to waste time searching for one to enjoy. Our app recommends movies based on user-selected genre tags and learns from ratings to improve suggestions over time.

**Status:** defined

---

### 2. Data via API / Database

> The application uses some data that is loaded via an API and/or provided via a database.

**Our approach:** TMDB API v3 — free, widely used, 158 API endpoints. Key endpoints: `/discover/movie` (genre-filtered results), `/trending/movie/{time_window}` (trending), `/movie/{id}` (details), `/genre/movie/list` (genre catalog), `/search/movie` (text search by title), `/movie/{id}/watch/providers` (streaming availability). Local SQLite database persists ratings (INTEGER 0-100), mood reactions, watchlist, and dismissals across sessions. Schema versioned via `PRAGMA user_version`.

**Status:** implemented

---

### 3. Data Visualization

> The application visualizes some data that serves the use case.

**Our approach:** Statistics dashboard with KPI metrics (watch hours, avg runtime, rated/watchlisted/dismissed counts, avg rating), 7 Altair charts (genre distribution, decade distribution, language distribution, rating distribution histogram, user vs TMDB scatter plot, rating history line chart, mood distribution), top 5 directors + actors rankings, and sortable rated movies table with poster thumbnails. All data from normalized SQLite tables (zero API calls). Movie details + keywords eagerly cached on rating save + backfilled on startup.

**Status:** in progress (proof of concept — charts and data pipeline functional, layout and polish pending)

---

### 4. User Interaction

> The application allows for some user interaction, e.g., adding additional data, selecting certain data, running certain data analyses.

**Our approach:** Separated discover and rating flows across 4 pages. Discover: 14 filter controls (genre, mood, certification, year, language, runtime, score, votes, keywords, streaming country/provider) with 4 sort options including personalized ML scoring. Filters passed to TMDB API `/discover/movie`; mood filter + personalized ranking run locally against precomputed `.npy` arrays. Rate: TMDB text search + Netflix-style clickable poster grid, click opens `@st.dialog` with details + 0-100 rating slider (steps of 10) + 7 mood reaction buttons (Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry). Watchlist: poster grid, click → dialog with streaming providers, "Remove" or "Mark as watched" with rating slider + mood reactions. Statistics: KPI dashboard, charts (genre, language, decade, rating, mood distribution), directors/actors rankings, rated movies table. All actions persist to SQLite immediately.

**Status:** in progress — redesign from 2026-03-25, implementation pending

---

### 5. Machine Learning

> The application implements some machine learning.

**Our approach:** Personalized movie recommendations combining content-based filtering with user feedback. Users rate movies (0-100) and tag mood reactions (7 categories: Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry — TMDB Vibes / Ekman model). The system builds a user profile from rating history and computes personalized scores for candidate movies using multiple similarity signals: keyword TF-IDF/SVD similarity, mood match, director/actor SVD similarity, decade/language/runtime preference, quality score (Bayesian average), and contra-penalty from low-rated films. All feature vectors derived from `tmdb.sqlite` (~1.17M movies, 30 normalized tables). Offline pipeline: feature extraction (sklearn TF-IDF + TruncatedSVD), mood score prediction (genre->mood + keyword->mood mapping + emotion classifier on overview/review text), quality scores. See [ML-PIPELINE.md](ML-PIPELINE.md) for full architecture.

**Course-mandated ML evaluation checklist:**

- [ ] `train_test_split(stratify=y, random_state=42)` — stratified, reproducible
- [ ] Data scaling with `RobustScaler` (fit on train, transform train+test)
- [ ] 5+ classifier comparison in a pandas DataFrame:
  - [ ] `KNeighborsClassifier`
  - [ ] `SVC`
  - [ ] `GaussianNB`
  - [ ] `LogisticRegression`
  - [ ] `MLPClassifier`
  - [ ] `DummyClassifier(strategy="most_frequent")` — baseline
  - [ ] `DummyClassifier(strategy="stratified")` — baseline
- [ ] Metrics: accuracy, precision (macro), recall (macro), F1 (macro) per classifier
- [ ] Scaled vs unscaled comparison (following assignment-11 pattern)
- [ ] `ConfusionMatrixDisplay.from_predictions(y_test, y_pred)` for best model
- [ ] `classification_report(y_test, y_pred)` for best model
- [ ] `KFold(n_splits=10, shuffle=True)` + `cross_val_score` — mean +/- std
- [ ] KNN hyperparameter tuning (k=1..20, accuracy vs k plot)

**Beyond course level (score 3 differentiators):**

- TF-IDF + TruncatedSVD on 1.17M movies (70K+ keywords, 170K+ directors)
- Content-based scoring with 9 weighted signals + dynamic weight shifting
- Pre-trained transformer for emotion classification on movie text
- Bayesian average quality scoring
- Offline pipeline producing ~3 GB of precomputed .npy feature arrays

**Status:** in progress — architecture designed, offline pipeline and scoring implementation pending

---

### 6. Code Documentation

> The source code is well documented by comments in the source code.

**Our approach:** Google-style docstrings on all functions and modules, inline comments for non-obvious logic, API calls commented with endpoint and purpose, session state operations documented.

**Status:** in progress

---

### 7. Contribution Matrix

> The contributions of each team member are documented (e.g., contribution matrix).

**Our approach:** See [CONTRIBUTION.md](CONTRIBUTION.md).

**Status:** not started

---

### 8. Video

> The result is presented and demoed in a 4-minute video. The video is not allowed to use AI-generated voice overs.

**Our approach:** 4-minute screen recording with live narration by team members. Covers problem, approach, demo, contributions. **No AI-generated voice overs allowed** — all narration must be recorded by team members.

**Status:** not started

---

## Grade Calculation

| Points | Grade % | Points | Grade % |
|--------|---------|--------|---------|
| 0      | 0%      | 9      | 56.25%  |
| 1      | 6.25%   | 10     | 62.5%   |
| 2      | 12.5%   | 11     | 68.75%  |
| 3      | 18.75%  | 12     | 75%     |
| 4      | 25%     | 13     | 81.25%  |
| 5      | 31.25%  | 14     | 87.5%   |
| 6      | 37.5%   | 15     | 93.75%  |
| 7      | 43.75%  | ≥16    | 100%    |
| 8      | 50%     |        |         |
