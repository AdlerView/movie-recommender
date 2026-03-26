# MIGRATION.md

Migration plan for the movie recommender app. The existing ML pipeline
and UI are being replaced. This document defines the new architecture,
data flows, scoring system, ML pipeline, and implementation roadmap.

**Created:** 2026-03-25
**Updated:** 2026-03-26

---

## Architecture Overview

The system has two phases with strict separation:

---

### Offline Phase (Training) `PENDING`

Uses the 8.2 GB TMDB SQLite database (`store/tmdb.db`, 1.17M movies,
30 tables) to precompute feature vectors and mood scores. This database
is never queried at runtime.

---

### Runtime Phase (Production) `PARTIAL`

Uses three data sources:

1. **TMDB API** -- live calls for search, discovery, movie details,
   configuration (genres, languages, certifications, providers) `DONE`
2. **Precomputed model files** (~3 GB `.npy` arrays) -- feature vectors
   and mood scores for all 1.17M movies, indexed by movie ID `PENDING`
3. **Local user database** (~1 KB) -- ratings, mood tags, streaming
   subscriptions, cached user profile vectors `DONE`

---

## UI Flows

---

### Flow 1: Rate a Movie `DONE`

The user rates a movie after watching it.

**Steps:**

1. User searches for a movie (text input)
2. User gives a rating (0-100 in steps of 10)
3. User selects one or more moods: Happy, Interested, Surprised, Sad,
   Disgusted, Afraid, Angry
4. User saves

**Data stored:**

```
{movie_id: 550, rating: 80, moods: ["surprised", "interested"], rated_at: "2026-03-25T..."}
```

**After saving:** the user profile vectors are recomputed from all
ratings using the precomputed model files. *(Profile recomputation
not yet implemented -- requires `user_profile.py` + `store/`.)*

---

### Flow 2: Discover a Movie `PENDING`

The user wants to find a new movie to watch.

**UI elements:**

| # | Element | Type | Source | Required |
|---|---|---|---|---|
| 1 | Mood | 7 toggle buttons | Hardcoded (own concept) | Optional, multi-select |
| 2 | Sort | Dropdown | Hardcoded (4 options) | Default: Personalized Score |
| 3 | Genre | 19 toggle buttons | TMDB API `genre/movie/list` | Required, min 1 |
| 4 | Certification | Toggle buttons (values change per country, e.g. DE: 0/6/12/16/18, US: G/PG/PG-13/R/NC-17) | TMDB API `certification/movie/list` | Optional |
| 5 | Release date from | Year input | -- | Optional |
| 6 | Release date to | Year input | -- | Optional |
| 7 | Language | Dropdown | TMDB API `configuration/languages` | Optional |
| 8 | Runtime | Range slider 0-360 min | -- | Optional, default 0-360 |
| 9 | User score | Range slider 0-10 | -- | Optional, default 0-10 |
| 10 | Min user votes | Slider 0-500 | -- | Optional, default 50 |
| 11 | Keywords | Text field + autocomplete | TMDB API `search/keyword` | Optional |
| 12 | Streaming country | Dropdown | TMDB API `configuration/countries` | Optional |
| 13 | Streaming providers | Multi-toggle | TMDB API `watch/providers/movie` | Optional |
| 14 | Only my subscriptions | Checkbox | Local user DB | Optional |

*Current state: Discover has genre-only filter + card browsing. The
14-filter UI, mood filter, and personalized scoring are not yet
implemented.*

**Sort options:**

| Option | Logic |
|---|---|
| Personalized Score (default) | ML scoring pipeline |
| Popularity descending | `sort_by=popularity.desc` on discover API |
| Rating descending | `sort_by=vote_average.desc` on discover API |
| Release date descending | `sort_by=primary_release_date.desc` on discover API |

**Results display per movie:**

- Title, year, poster
- Genres, runtime, certification badge
- Predicted mood tags
- Streaming provider logos
- Personalized score (0-100)

---

## API Calls `PARTIAL`

---

### App Startup (cached, 24h TTL) `PARTIAL`

7 calls, executed once and cached:

```
GET /3/configuration                            24h   PENDING
GET /3/genre/movie/list?language=en             24h   DONE (used by Discover)
GET /3/configuration/languages                  24h   PENDING
GET /3/certification/movie/list                 24h   PENDING
GET /3/watch/providers/movie?watch_region=DE    24h   PARTIAL (used by Watchlist, not Discover)
GET /3/watch/providers/regions?language=en       24h   PENDING
GET /3/configuration/countries?language=en       24h   PENDING
```

The provider call is re-fetched when the user changes their streaming
country.

---

### Flow 1: Rate a Movie `DONE`

```
GET /3/search/movie?query={text}&language=en-US&page=1   5m
GET /3/movie/{id}?language=en-US                         1h
GET /3/movie/{id}/keywords                               24h
```

3 calls per rating action. Keywords are fetched on save for caching
in the local database (used for keyword badges and ML pipeline).

---

### Flow 2: Discover a Movie `PENDING`

**Keyword autocomplete (debounced 300ms per keystroke):**

```
GET /3/search/keyword?query={text}&page=1
```

**Candidate retrieval (on "Discover" click):**

```
GET /3/discover/movie
    ?with_genres=53,18
    &certification_country=DE
    &certification.lte=16
    &primary_release_date.gte=2000-01-01
    &primary_release_date.lte=2025-12-31
    &with_original_language=en
    &with_runtime.gte=90
    &with_runtime.lte=180
    &vote_average.gte=6
    &vote_count.gte=100
    &with_keywords=10349
    &watch_region=DE
    &with_watch_providers=8|337
    &with_watch_monetization_types=flatrate
    &sort_by=popularity.desc
    &page=1
```

1-5 pages fetched depending on desired candidate pool (20 results per
page).

**Detail enrichment (parallel, for scored top-20):**

```
GET /3/movie/{id}?append_to_response=watch/providers,videos,release_dates,credits
```

20 parallel calls. Each provides: streaming providers per country,
trailer links, certifications, director + top cast.

**Total per discovery request:** ~25 API calls, ~500ms with parallel
execution. Well within the 40 req/s rate limit.

---

### What the TMDB API handles vs. what runs locally

| Feature | TMDB API | Local |
|---|---|---|
| Genre filter | `with_genres` | -- |
| Keyword filter | `with_keywords` | -- |
| Certification filter | `certification` | -- |
| Year filter | `primary_release_date` | -- |
| Language filter | `with_original_language` | -- |
| Runtime filter | `with_runtime` | -- |
| Score filter | `vote_average` | -- |
| Vote count filter | `vote_count` | -- |
| Provider filter | `with_watch_providers` | -- |
| **Mood filter** | -- | **mood_scores.npy** |
| **Personalized ranking** | -- | **all .npy + user DB** |
| **Contra penalty** | -- | **keyword_svd + user DB** |

---

## Scoring System `PENDING`

---

### Request Flow

```
User clicks "Discover"
    |
    v
1. TMDB API: discover/movie with all filters
   -> ~100-500 candidate movie IDs + basic data
    |
    v
2. Mood filter (local, only if user selected a mood)
   For each candidate: mood_scores.npy[movie_id_index[id]]
   Keep only movies where selected mood > 0.3
   -> ~50-300 candidates
   Fallback: if fewer than 20 candidates remain, lower threshold
   stepwise (0.2, 0.1, 0.0) until at least 20 candidates or
   threshold reaches 0. This prevents empty results for rare moods
   like "Disgusted".
    |
    v
3. Scoring depends on selected sort order:
   - "Personalized Score": full ML scoring (see formula below)
   - "Popularity": use TMDB popularity from discover response
   - "Rating": use TMDB vote_average from discover response
   - "Release date": use TMDB release_date from discover response
   Mood filter from step 2 applies to ALL sort orders.
   Non-personalized sorts skip the ML scoring entirely.
    |
    v
4. Sort + return top-20
   Display data from discover response + mood scores from npy
```

---

### Scoring Formula

```
final_score(movie) =
    0.25 * keyword_similarity
  + 0.20 * mood_match
  + 0.15 * director_similarity
  + 0.10 * actor_similarity
  + 0.05 * decade_similarity
  + 0.03 * language_similarity
  + 0.02 * runtime_similarity
  + 0.10 * quality_score
  + 0.10 * contra_penalty
  -----
  = 1.00
```

---

### Component Details

**Keyword Similarity (0.25):**

Cosine similarity between the user's keyword preference vector and
the candidate's keyword vector. The user vector is a weighted average
of keyword SVD vectors from all rated movies, where the weight is the
normalized rating: `(rating - 50) / 50`. A rating of 100 gives weight
+1.0, rating 0 gives -1.0, rating 50 gives 0.0.

**Mood Match (0.20):**

If the user selected a mood explicitly: average of the candidate's
predicted mood scores for the selected moods.

If no mood selected: dot product between the user's implicit mood
vector (normalized frequency of mood tags from rating history) and
the candidate's mood scores.

**Director Similarity (0.15):**

Same logic as keyword similarity but using director SVD vectors.
Captures: "user likes Fincher" automatically boosts Villeneuve and
Nolan because their director vectors are nearby in the reduced space.

**Actor Similarity (0.10):**

Same logic using actor SVD vectors. Only top-5 cast per film (by
`cast_order`) to reduce noise from extras.

**Decade Similarity (0.05):**

Cosine similarity between user's decade preference (weighted average
of decade onehot vectors from rated movies) and candidate's decade.

**Language Similarity (0.03):**

Same logic using language onehot vectors (top-20 languages).

**Runtime Similarity (0.02):**

`1.0 - abs(user_avg_runtime - candidate_runtime) / 360.0`

User average runtime is computed from positively-rated movies only
(rating > 50).

**Quality Score (0.10):**

Bayesian average, precomputed:

```
m = median(all_vote_counts)
C = mean(all_vote_averages)
quality = (vote_count * vote_avg + m * C) / (vote_count + m)
```

Normalized to [0, 1].

**Contra Penalty (0.10):**

Negative cosine similarity between the contra vector (average keyword
SVD vector from movies rated below threshold) and the candidate's
keyword vector. Demotes movies that are thematically similar to
disliked movies.

Sources for the contra vector:
- Movies with ratings below 40/100 (ratings 0-30)
- Dismissed movies ("not interested") -- treated as negative signal
  in Layer 2 (online scoring). Exact weight TBD during scoring.py
  implementation. Not used in offline pipeline (Layer 1).

---

### Dynamic Weights by Rating Count

The scoring weights shift based on how many movies the user has rated.
With few ratings, quality dominates. With many ratings, personalization
dominates.

| Rated Films | Keyword | Mood | Director | Actor | Decade | Language | Runtime | Quality | Contra |
|---|---|---|---|---|---|---|---|---|---|
| 0 (cold start) | 0.00 | 0.40 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.60 | 0.00 |
| 1-9 | 0.10 | 0.25 | 0.05 | 0.03 | 0.02 | 0.01 | 0.01 | 0.50 | 0.03 |
| 10-49 | 0.20 | 0.22 | 0.12 | 0.08 | 0.04 | 0.02 | 0.02 | 0.20 | 0.10 |
| 50+ (full) | 0.25 | 0.20 | 0.15 | 0.10 | 0.05 | 0.03 | 0.02 | 0.10 | 0.10 |

---

## ML Pipeline `PENDING`

---

### Offline Pipeline (run once, then on DB updates) `PENDING`

---

#### Stage 1: Feature Extraction `PENDING`

Input: `store/tmdb.db` (8.2 GB, 1.17M movies)

| Feature | Dimensions | DB Source |
|---|---|---|
| Keyword TF-IDF -> SVD | 1.17M x 200 | `movie_keywords` + `keywords` |
| Genre onehot | 1.17M x 19 | `movie_genres` + `genres` |
| Director onehot -> SVD | 1.17M x 200 | `movie_crew` WHERE `job = 'Director'` |
| Actor onehot -> SVD | 1.17M x 200 | `movie_cast` WHERE `cast_order < 5` |
| Decade onehot | 1.17M x 15 | `movies.release_date` -> decade bins |
| Language onehot | 1.17M x 20 | `movies.original_language` top-20 |
| Runtime normalized | 1.17M x 1 | `movies.runtime / 360.0` |
| Movie ID index | 1.17M entries | `movies.id` -> row index mapping |

Output: `.npy` files + `movie_id_index.json` + `svd_models/*.pkl`

Script: `pipeline/01_extract_features.py`

---

#### Stage 2: Mood Score Prediction `PENDING`

For each movie: 7 mood probabilities (happy, interested, surprised,
sad, disgusted, afraid, angry).

**Signal 1: Genre -> Mood mapping (19 manual rules)**

Independent scores per genre (not normalized to 1.0). Canonical
source: `store/genre_mood_map.json`.

```
Comedy      -> {happy: 0.8, surprised: 0.2}
Horror      -> {afraid: 0.7, disgusted: 0.3}
Drama       -> {sad: 0.5, interested: 0.4}
Thriller    -> {afraid: 0.5, interested: 0.4, surprised: 0.2}
Romance     -> {happy: 0.6, sad: 0.3}
War         -> {angry: 0.5, sad: 0.5, afraid: 0.2}
Crime       -> {angry: 0.4, interested: 0.4, afraid: 0.2}
Documentary -> {interested: 0.6, sad: 0.2, angry: 0.1}
...           (full list in genre_mood_map.json)
```

**Signal 2: Keyword -> Mood mapping (supervised pipeline, ~70K
keywords)**

Produced by `pipeline/keyword_mood_classifier.py`. Two-stage process:
1. Labeled seed: 5,000 keywords in
   `data/labeled/tmdb-keyword-frequencies_labeled_top5000.tsv` (1,049 single-
   label after review, 1,634 multi, 2,317 none)
2. Train classifier on single-label subset (1,049), infer remaining
   70K+

**Signal 3: Emotion classifier on overview text**

Model: `j-hartmann/emotion-english-distilroberta-base`
Input: `movies.overview` + `movies.tagline`
Output: `{anger, disgust, fear, joy, sadness, surprise}`
Mapped to 7 moods. "interested" derived from classifier confidence.

**Signal 4: Emotion classifier on reviews (3.3% of movies)**

Same classifier on `movie_reviews.content`. Average across all reviews
per movie.

**Combination (dynamic weighting):**

```
If reviews available:
    0.50 * reviews + 0.20 * overview + 0.20 * genre + 0.10 * keywords

If no reviews:
    0.50 * overview + 0.30 * genre + 0.20 * keywords
```

Output: `mood_scores.npy` (1.17M x 7)

Script: `pipeline/02_predict_moods.py`

---

#### Stage 3: Quality Scores `PENDING`

Bayesian average for each movie:

```
m = median(all_vote_counts)
C = mean(all_vote_averages)
quality = (v * R + m * C) / (v + m)
```

Normalized to [0, 1].

Output: `quality_scores.npy` (1.17M x 1)

Script: `pipeline/03_quality_scores.py`

---

#### Stage 4: Save Mappings `PENDING`

Output:

```
store/
  genre_mood_map.json        19 entries
  keyword_mood_map.json      ~70K entries
  movie_id_index.json        1.17M entries
  svd_models/
    keyword_svd.pkl
    director_svd.pkl
    actor_svd.pkl
```

Script: `pipeline/04_build_index.py`

---

### Keyword-to-Mood Classifier `DONE`

Supervised pipeline that maps TMDB keywords to mood categories. This
is a productive pipeline step (Phase 1b) -- the academic evaluation
of the same workflow belongs in Phase 3.

**Phase 1b scope (build / train / select / infer):**

- Load labeled TSV, filter to `assignment_type == "single"` (1,049)
- Feature extraction: sentence embeddings (EmbeddingGemma-300M, 768-dim)
  and/or TF-IDF baseline
- `train_test_split(stratify=y, random_state=42)`
- Optional scaling (RobustScaler)
- Train 5+ classifiers: KNN, SVC, GaussianNB, LogisticRegression,
  MLPClassifier, DummyClassifier
- Select best model by macro-F1
- Fit best model on full single-label training set
- Infer mood labels for all remaining 70K+ unlabeled keywords
- Export: `store/keyword_mood_map.json`

**Phase 3 scope (evaluate / visualize / report):**

- Reproducible evaluation of the Phase 1b workflow
- `classification_report`, confusion matrix, macro-F1
- Cross-validation (KFold, n_splits=10)
- KNN hyperparameter tuning (k=1..20 plot)
- Scaled vs. unscaled comparison
- Notebook narrative + Statistics page section

Script: `pipeline/keyword_mood_classifier.py`

---

### Online Pipeline (per request) `PENDING`

```
1. TMDB API discover/movie with all user filters
   -> ~100-500 candidate IDs

2. For each candidate: look up precomputed vectors from .npy files
   using movie_id_index.json

3. Compute user profile (if not cached):
   - Load user_ratings + user_rating_moods from local DB
   - user_keyword_vec  = weighted_avg(keyword_svd[rated], ratings)
   - user_director_vec = weighted_avg(director_svd[rated], ratings)
   - user_actor_vec    = weighted_avg(actor_svd[rated], ratings)
   - user_decade_vec   = weighted_avg(decade_vec[rated], ratings)
   - user_language_vec = weighted_avg(language_vec[rated], ratings)
   - user_runtime_pref = weighted_avg(runtimes[rated], positive_ratings)
   - user_implicit_mood = normalized mood tag frequencies
   - user_contra_vec   = avg(keyword_svd[rated where rating < 40])

4. Batch-score all candidates (numpy, vectorized, ~50ms)

5. Sort by score, return top-20

6. Fetch movie details for top-20 via TMDB API (parallel):
   GET /3/movie/{id}?append_to_response=watch/providers,videos,release_dates,credits
```

---

## Data Stores

---

### Offline Only (not shipped to production)

```
store/tmdb.db                    8.2 GB    Full TMDB database, 30 tables, 1.17M movies
```

---

### Runtime: Model Files (read-only) `PENDING`

```
store/
  keyword_svd_vectors.npy       1.17M x 200    float32
  director_svd_vectors.npy      1.17M x 200    float32
  actor_svd_vectors.npy         1.17M x 200    float32
  genre_vectors.npy             1.17M x 19     float32
  decade_vectors.npy            1.17M x 15     float32
  language_vectors.npy          1.17M x 20     float32
  runtime_normalized.npy        1.17M x 1      float32
  mood_scores.npy               1.17M x 7      float32
  quality_scores.npy            1.17M x 1      float32
  movie_id_index.json           1.17M entries  movie_id <-> row index
  genre_mood_map.json           19 entries     manual genre -> mood rules
  keyword_mood_map.json         ~70K entries   supervised keyword -> mood predictions
  svd_models/
    keyword_svd.pkl                            for transforming new movies
    director_svd.pkl
    actor_svd.pkl
```

Total: ~3 GB

---

### Runtime: User Database (read-write, local) `DONE`

```sql
CREATE TABLE user_ratings (
    movie_id   INTEGER PRIMARY KEY,
    rating     INTEGER NOT NULL CHECK (rating BETWEEN 0 AND 100),  -- 0-100 in steps of 10
    rated_at   TEXT NOT NULL
);

CREATE TABLE user_rating_moods (
    movie_id   INTEGER NOT NULL,
    mood       TEXT NOT NULL,
    PRIMARY KEY (movie_id, mood)
);

CREATE TABLE user_subscriptions (
    provider_id INTEGER PRIMARY KEY,
    iso_3166_1  TEXT NOT NULL
);

CREATE TABLE user_profile_cache (
    key   TEXT PRIMARY KEY,
    value BLOB
);
```

---

## Project Structure

The canonical directory structure is defined in [CLAUDE.md](CLAUDE.md)
§ Directory Structure. See that section for the full tree.
    tmdb-schema.mmd                  ER diagram of TMDB database
```

---

## ML Evaluation (Course Requirement 5) `PENDING`

The ML evaluation follows the exact workflow taught in lectures 10-11
and assignments 10-11. See [docs/ML-PIPELINE.md](docs/ML-PIPELINE.md)
for the full specification.

**Two classification tasks:**

1. **User preference:** Binary -- predict "liked" (>= 60/100) vs
   "disliked" (< 60/100) from 9 scoring-component feature vectors
2. **Keyword-to-mood:** Multi-class -- predict mood category from
   sentence embeddings of TMDB keywords (70K+ keywords, 7 moods)

Both follow the same course-compliant evaluation workflow.

**Shared utility:** `app/utils/ml_eval.py` contains all evaluation
logic. Called by both the Statistics page (compact, video-friendly)
and `notebooks/ml_evaluation.ipynb` (academic, narrative). No
duplicated code.

**Mandatory elements (course baseline):**

1. Stratified train/test split with fixed random_state
2. Data scaling (RobustScaler, fit on train only)
3. 5+ classifier comparison (KNN, SVC, GaussianNB, LogisticRegression,
   MLPClassifier) + DummyClassifier baselines
4. Metrics DataFrame: accuracy, precision, recall, F1 (macro)
5. Confusion matrix + classification_report for best model
6. 10-fold cross-validation with mean +/- std
7. Scaled vs. unscaled comparison
8. KNN hyperparameter tuning (k=1..20 plot)

**Beyond course (for score 3):**

- TF-IDF + TruncatedSVD on 1.17M movies
- Content-based scoring with 9 weighted signals
- Pre-trained emotion transformer
- Dynamic weight shifting by rating count
- Supervised keyword-to-mood pipeline (embeddings + classifier)

---

## Implementation Roadmap

Phased implementation plan. Each task has a unique ID, status, file
targets, and dependency chain. Status tags: `DONE`, `IN PROGRESS`,
`PENDING`.

**Design principle:** Phase 1b (keyword classifier) produces the
productive pipeline output (`keyword_mood_map.json`). Phase 3 produces
the academic evaluation of the same workflow (confusion matrix,
cross-validation, notebook). No duplicated training -- Phase 3
evaluates what Phase 1b built.

---

### Phase 0: Foundation `DONE`

Completed 2026-03-26. DB schema v5, rating slider 0-100, mood reaction
buttons, old keyword/mood pipeline code removed. See TODO.md "Done"
section for details.

---

### Phase 1a: Offline Pipeline `PENDING`

Produces `store/` directory with precomputed feature arrays. Reads
from `store/tmdb.db` (8.2 GB, offline only). Each pipeline stage is
idempotent and can be re-run independently.

| ID | Task | File(s) | Depends on | Status |
|---|---|---|---|---|
| 1a.1 | Create `genre_mood_map.json` (19 genre-to-mood rules) | `store/genre_mood_map.json` | -- | `DONE` |
| 1a.2 | Feature extraction: keyword TF-IDF/SVD, director/actor SVD, genre/decade/language onehot, runtime | `pipeline/01_extract_features.py` -> 7 `.npy` + `movie_id_index.json` + `.pkl` | `store/tmdb.db` | `PENDING` |
| 1a.3 | Quality scores: Bayesian average, normalize to [0,1] | `pipeline/03_quality_scores.py` -> `quality_scores.npy` | `store/tmdb.db` | `PENDING` |
| 1a.4 | Mood prediction: 4 signals (genre + keyword + overview emotion + review emotion), dynamic weighting | `pipeline/02_predict_moods.py` -> `mood_scores.npy` | 1a.1, 1b.1, `store/tmdb.db` | `PENDING` |
| 1a.5 | Build index: verify all model files, save final mappings | `pipeline/04_build_index.py` | 1a.2, 1a.3, 1a.4 | `PENDING` |

**Runtime estimates:**
- 1a.2: ~2h code + several hours pipeline runtime (keyword TF-IDF peaks ~8 GB RAM)
- 1a.3: ~30 min (simplest stage)
- 1a.4: ~2h code + 4-8h runtime (emotion classifier on ~1M texts, requires `transformers` + `torch`)

**Parallelizable:** 1a.1 + 1a.2 + 1a.3 can start simultaneously.
1a.4 needs 1a.1 and 1b.1 outputs. 1a.5 needs everything.

---

### Phase 1b: Keyword-to-Mood Classifier `DONE`

Completed 2026-03-26. Supervised classifier trained on 1,049
single-label keywords (EmbeddingGemma-300M, 768-dim), best model
MLPClassifier (val F1=0.76, test accuracy=78%), inferred moods for
65,779 unlabeled keywords. Total: 68,462 entries in
`store/keyword_mood_map.json`. Script: `pipeline/keyword_mood_classifier.py`.
Evaluation artifacts: `data/evaluation/keyword_classifier_*.{csv,png}`.
See TODO.md "Done" section for details.

---

### Phase 2: Online Scoring `PENDING`

Connects `store/` to the running app. Computes user profiles from
ratings, scores candidate movies, builds TMDB API parameters from
filter UI.

| ID | Task | File(s) | Depends on | Status |
|---|---|---|---|---|
| 2.1 | User profile: load `.npy` arrays, compute weighted-average profile vectors from ratings, cache in `user_profile_cache` | `app/utils/user_profile.py` | 1a.5 (`store/` populated) | `PENDING` |
| 2.2 | Scoring: 9-signal formula, dynamic weights by rating count, batch cosine similarity (numpy vectorized) | `app/utils/scoring.py` | 2.1 | `PENDING` |
| 2.3 | Filters: TMDB API parameter builder from 14 filter controls, local mood filter against `mood_scores.npy` | `app/utils/filters.py` | 1a.5 (`store/` for mood filter) | `PENDING` |

**Graceful degradation:** When `store/` is not populated, the app
MUST fall back to quality + mood only (cold-start weight table row 0:
0.60 quality + 0.40 mood). Personalized scoring is
disabled until `store/` exists.

---

### Phase 3: ML Evaluation (Course Requirement 5) `PENDING`

Academic evaluation of the ML workflows built in Phase 1b and Phase 2.
Produces course-compliant output: metrics, plots, tables, notebook.
No duplicated training -- evaluates what was already built.

| ID | Task | File(s) | Depends on | Status |
|---|---|---|---|---|
| 3.1 | Shared ML evaluation utility: `evaluate_classifiers()`, `best_model_report()`, `run_cross_validation()` | `app/utils/ml_eval.py` | 1b.1 (keyword classifier), 2.2 (scoring) | `PENDING` |
| 3.2 | Statistics page: ML Evaluation section -- "Run ML Evaluation" button, classifier comparison table, confusion matrix, classification report, CV scores, best model KPIs | `app/app_pages/statistics.py` | 3.1 | `PENDING` |
| 3.3 | Jupyter notebook: academic narrative -- problem definition, feature engineering, data distribution plots, all classifiers with commentary, scaled vs. unscaled, KNN k=1..20 plot, discussion | `notebooks/ml_evaluation.ipynb` | 3.1 | `PENDING` |

**Phase 3 evaluation scope (both classification tasks):**

1. **Keyword-to-mood** (from Phase 1b): `classification_report`,
   confusion matrix, macro-F1, cross-validation, KNN k-plot, scaled
   vs. unscaled comparison
2. **User preference** (from Phase 2): binary classification
   (liked >= 60 vs disliked < 60), 9 scoring features, same
   evaluation workflow. Requires >= 50 user ratings for meaningful
   results.

---

### Phase 4: UI Integration `PENDING`

Rebuild Discover page with 14 filters and personalized scoring.
Add personalized poster grid to Rate page. Add mood reactions to
Watchlist.

| ID | Task | File(s) | Depends on | Status |
|---|---|---|---|---|
| 4.1 | Discover: 14 filter controls (genre, mood, certification, year, language, runtime, score, votes, keywords, streaming) | `app/app_pages/discover.py` | 2.3 (filters.py) | `PENDING` |
| 4.2 | Discover: personalized sort option (ML scoring from rating history) | `app/app_pages/discover.py` | 2.2 (scoring.py), 4.1 | `PENDING` |
| 4.3 | Rate: "Based on your interests" poster grid (personalized recommendations, falls back to trending) | `app/app_pages/rate.py` | 2.2 (scoring.py) | `PENDING` |
| 4.4 | Watchlist: mood reactions in "Mark as watched" dialog | `app/app_pages/watchlist.py` | 0.1 (DB schema) | `PENDING` |
| 4.5 | Statistics: mood distribution chart from user reactions | `app/app_pages/statistics.py` | 0.3 (mood buttons) | `PENDING` |

---

### Phase 5: Polish and Deliverables `PENDING`

Final quality pass and submission artifacts. Deadline: 2026-05-14.

| ID | Task | File(s) | Depends on | Status |
|---|---|---|---|---|
| 5.1 | Statistics dashboard polish -- layout, chart interactions, visual design | `app/app_pages/statistics.py` | 3.2, 4.5 | `PENDING` |
| 5.2 | Code documentation final pass (Req 6) -- docstrings, inline comments on all new files | all `.py` files | all phases | `PENDING` |
| 5.3 | Contribution matrix (Req 7) | `docs/CONTRIBUTION.md` | -- | `PENDING` |
| 5.4 | Record 4-minute video with live narration (Req 8) | video file | all phases | `PENDING` |
| 5.5 | Final code review + Canvas upload by 23:59 | -- | 5.1-5.4 | `PENDING` |

---

### Dependency Graph

```
Phase 0 (DONE)
  0.1 DB schema ─────────────────────────────────────────┐
  0.2 Rating slider ─────────────────────────────────────┤
  0.3 Mood buttons ──────────────────────────────────────┤
  0.4 Phase 1 cleanup ──────────────────────────────────┤
                                                          │
Phase 1a + 1b (parallel start)                           │
  1a.1 genre_mood_map.json ──────────────┐               │
  1b.1 keyword_mood_classifier.py ───────┤               │
  1a.2 01_extract_features.py ───────────┤               │
  1a.3 03_quality_scores.py ─────────────┤               │
                                          v               │
  1a.4 02_predict_moods.py ──────────────┤               │
                                          v               │
  1a.5 04_build_index.py                 │               │
           |                              │               │
           v                              │               │
Phase 2                                   │               │
  2.1 user_profile.py ───────────────────┤               │
  2.2 scoring.py ────────────────────────┤               │
  2.3 filters.py ────────────────────────┤               │
           |                              │               │
           v                              │               │
Phase 3 (academic evaluation)            │               │
  3.1 ml_eval.py ────────────────────────┤               │
  3.2 Statistics ML section ─────────────┤               │
  3.3 ML evaluation notebook             │               │
           |                              │               │
           v                              │               │
Phase 4 (UI integration)                 │               │
  4.1 Discover 14 filters ───────────────┤               │
  4.2 Discover personalized sort ────────┤               │
  4.3 Rate "Based on interests" ─────────┤               │
  4.4 Watchlist mood reactions ──────────┘ <──── 0.1 ────┘
  4.5 Statistics mood chart ───────────── <──── 0.3
           |
           v
Phase 5 (polish + deliverables)
  5.1 Statistics polish
  5.2 Code documentation
  5.3 Contribution matrix
  5.4 Video recording
  5.5 Canvas upload (2026-05-14)
```

---

### Timeline

| Week | Date | Milestone | Tasks |
|---|---|---|---|
| Semester break | now | Start pipeline implementation | 1a.1, 1a.2, 1a.3, 1b.1 |
| 07 | 2026-04-16 | Coaching 13.04: show pipeline progress | 1a.4, 1a.5, 2.1-2.3 |
| 08 | 2026-04-23 | Scoring + filters functional | 4.1, 4.2, 4.3 |
| 09 | 2026-04-30 | ML evaluation complete | 3.1, 3.2, 3.3, 4.4, 4.5 |
| 10 | 2026-05-07 | Polish iteration | 5.1, 5.2, 5.3 |
| 11 | 2026-05-14 | Upload deadline 23:59 | 5.4, 5.5 |

---

### Open Questions

- **Pre-seeded ratings for demo:** The video needs >= 50 ratings for
  meaningful ML evaluation. Could seed manually or create a script.
- **transformers + torch dependency:** Stage 1a.4 requires ~2-4 GB
  install. Only needed offline, not at runtime.
- **Memory for pipeline:** Stage 1a.2 keyword TF-IDF peaks ~8 GB RAM.
  Mac mini handles this; MBA (16 GB) may struggle.
