# Requirements Mapping

> Maps each of the 8 course requirements to specific implementation artifacts.
> Source: [group-project.pdf](group-project.pdf), slide 4 "Anforderungen und Benotung".

## Scoring Scale

| Points | Description (German original) | English |
|--------|------------------------------|---------|
| 0 | Anforderung nicht erfüllt / Feature existiert nicht | Not met / does not exist |
| 1 | Einfache Umsetzung, formal vorhanden aber für die Problemlösung wenig relevant | Basic, formally present but not very relevant |
| 2 | Gute Umsetzung | Good implementation |
| 3 | Herausragende Umsetzung, deutlich über das Level dieses Kurses hinausgehend | Outstanding, far beyond course level |

---

## Requirement 1: Problem Clearly Stated

**Original (DE):** "Ein Problem, das durch die App gelöst wird, ist klar formuliert (z. B. ein Business- oder privater Anwendungsfall)."

**Status:** ✅ Implemented

**Evidence:**
- `README.md`: "With access to thousands of movies across all streaming platforms, it is easy to waste time searching for one to enjoy."
- `docs/original-concept.md`: Full problem statement with use cases
- App solves the stated problem: personalized discovery reduces aimless scrolling

**Files:** `README.md`, `docs/original-concept.md`

**Estimated Score:** 3/3 — Problem is clearly defined, the app directly addresses it with personalized ML-based recommendations that go far beyond simple filtering.

---

## Requirement 2: Data via API/Database

**Original (DE):** "Die App verwendet Daten, die über eine API geladen und/oder über eine Datenbank/Datenbank-Management-System bereitgestellt werden."

**Status:** ✅ Implemented

**Evidence:**
- TMDB API v3: 9 endpoints (discover, search, details, keywords, genres, languages, certifications, countries, providers)
- SQLite user database: 8 tables (ratings, moods, watchlist, dismissed, subscriptions, preferences, profile cache, movie details with JSON columns)
- Offline pipeline database: tmdb.sqlite (7.7 GB, 1.17M movies, 30 tables)
- Precomputed `.npy` arrays (~3 GB) loaded at runtime

**Files:** `src/tmdb.py` (API client), `src/db.py` (SQLite layer), `ml/scoring/arrays.py` (array loading)

**Estimated Score:** 3/3 — Extensive API usage with caching, plus both online (user.sqlite) and offline (tmdb.sqlite) databases. JSON columns, WAL mode, and precomputed ML arrays go far beyond basic database usage.

---

## Requirement 3: Data Visualization

**Original (DE):** "Die App visualisiert Daten in zur Problemlösung nützlicher Art und Weise."

**Status:** ✅ Implemented

**Evidence:**
- 4 KPI metrics (movies rated, watch hours, avg rating, watchlisted)
- Genre preferences: horizontal bar chart colored by avg rating (Altair)
- Mood profile: horizontal bar chart with emoji labels (Altair)
- You vs TMDB: scatter plot with diagonal reference line and trend regression (Altair)
- Top 5 directors + actors: profile photos with movie count and avg rating
- Sortable rated movies table with progress bar columns

**Files:** `src/views/statistics.py`

**Estimated Score:** 3/3 — Multiple chart types (bar, scatter with regression, KPIs), all serving the user's goal of understanding their taste profile. Altair for interactive charts exceeds basic matplotlib usage taught in course.

---

## Requirement 4: User Interaction

**Original (DE):** "Die App ermöglicht Benutzerinteraktionen, z. B. das Hinzufügen zusätzlicher Daten, die Auswahl bestimmter Daten, die Analyse bestimmter Daten."

**Status:** ✅ Implemented

**Evidence:**
- **Discover:** 8 sidebar filters, mood pills, sort dropdown, poster grid clicks, detail dialog with watchlist/dismiss actions
- **Rate:** Text search, poster grid clicks, 0-100 rating slider, 7 mood reaction pills
- **Watchlist:** Poster grid, remove/mark-as-watched actions, rating on watch completion
- **Settings:** Country selection, provider subscription toggles, language preference
- All interactions persist to SQLite and affect personalization

**Files:** `src/views/discover.py`, `src/views/rate.py`, `src/views/watchlist.py`, `src/views/settings.py`

**Estimated Score:** 3/3 — Rich multi-page interaction model with immediate persistence, personalization feedback loop, and graceful degradation. Far beyond a single-page form.

---

## Requirement 5: Machine Learning

**Original (DE):** "Die Anwendung implementiert ein maschinelles Lernen."

**Status:** ✅ Implemented

**Evidence:**
- **Offline pipeline:** TF-IDF + TruncatedSVD (1.17M movies × 200 dims), Bayesian quality scores, emotion classifier (distilroberta), keyword-to-mood classifier (7 classes, EmbeddingGemma-300M embeddings)
- **Online scoring:** 11-signal cosine similarity, dynamic weight shifting by rating count, mood filter with threshold fallback
- **Academic evaluation:** 7 classifier comparison (KNN, SVC, GaussianNB, LogisticRegression, MLPClassifier, 2× DummyClassifier), scaled vs unscaled, confusion matrix, 10-fold cross-validation, KNN hyperparameter tuning (k=1..20)
- **Course compliance:** train_test_split with stratify, RobustScaler, ConfusionMatrixDisplay, classification_report, KFold cross-validation — all mandatory elements present
- **Beyond course:** TruncatedSVD, pre-trained transformer, content-based scoring with 11 signals, dynamic weight shifting, Bayesian averaging

**Files:** `ml/extraction/extract_features.py`, `ml/classification/keyword_mood_classifier.py`, `ml/extraction/moods.py`, `ml/extraction/quality_scores.py`, `ml/scoring/scoring.py`, `ml/scoring/arrays.py`, `ml/scoring/profile.py`, `ml/scoring/cache.py`, `ml/scoring/mood_filter.py`, `ml/evaluation/ml_eval.py`

**Estimated Score:** 3/3 — Complete ML pipeline from feature extraction through scoring to evaluation. Multiple techniques beyond course content (SVD, transformers, Bayesian averaging, 11-signal scoring).

---

## Requirement 6: Code Documentation

**Original (DE):** "Der Quellcode ist durch Kommentare im Quellcode gut dokumentiert."

**Status:** ✅ Implemented

**Evidence:**
- Every `.py` file has a module-level docstring with `see X.md` references to canonical documentation
- Public functions have concise one-liner docstrings; trivial CRUD functions rely on self-documenting names
- Inline comments on non-trivial logic (filter conditions, ML formulas, CSS workarounds)
- Extensive Markdown documentation: 16 `.md` files covering architecture, data flow, API reference, ML pipeline
- DRY documentation: information lives in exactly one place (either .md or .py, not both)

**Files:** 29 `.py` files, 16 `.md` files

**Estimated Score:** 3/3 — Comprehensive documentation at every level (module, function, inline). Google-style docstrings throughout. Course connections explicitly noted.

---

## Requirement 7: Contribution Matrix

**Original (DE):** "Die Beiträge der einzelnen Teammitglieder sind dokumentiert (z. B. Contribution-Matrix)."

**Status:** ⚠️ In Progress

**Evidence:**
- `docs/CONTRIBUTION.md` exists with the matrix structure and legend
- Currently only @AdlerView has contributions filled in
- Other team members' contributions need to be documented before submission

**Files:** `docs/CONTRIBUTION.md`

**Estimated Score:** 1/3 (if submitted as-is) → 2-3/3 (if completed with all team members)

---

## Requirement 8: 4-Minute Video + Demo

**Original (DE):** "Das Ergebnis wird in einem 4-minütigen Video präsentiert und demonstriert. Das Video darf KEINE AI generierte Tonspur enthalten."

**Status:** ❌ Not Started

**Evidence:** No video file exists yet. Must be recorded before May 14 deadline.

**Note:** Video must NOT contain AI-generated voice track (explicit requirement).

**Estimated Score:** 0/3 (not yet created)

---

## Score Summary

| # | Requirement | Status | Estimated Score |
|---|-------------|--------|----------------|
| 1 | Problem clearly stated | ✅ | 3/3 |
| 2 | Data via API/database | ✅ | 3/3 |
| 3 | Data visualization | ✅ | 3/3 |
| 4 | User interaction | ✅ | 3/3 |
| 5 | Machine learning | ✅ | 3/3 |
| 6 | Code documentation | ✅ | 3/3 |
| 7 | Contribution matrix | ⚠️ | 1-3/3 |
| 8 | 4-minute video | ❌ | 0/3 |
| | **Total (current)** | | **16-18/24** |
| | **Total (if 7+8 completed)** | | **22-24/24** |

**Current grade range:** 16 points = 100% (if Req 7 stays minimal)
**Potential grade range:** 22-24 points = 100% (with completed video + contribution matrix)

> Note: ≥16 points = 100% of the project grade (20% of final course grade).
> The project already exceeds the maximum threshold even without video and contribution matrix.
