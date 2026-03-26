# ML-PIPELINE.md

Offline ML pipeline that transforms the TMDB SQLite database into
precomputed model files used at runtime for personalized scoring.

**Created:** 2026-03-26
**Updated:** 2026-03-26

---

## Course Expectations (Requirement 5: Machine Learning)

The course (4,125 Grundlagen und Methoden der Informatik, FS26) teaches ML
via scikit-learn in weeks 10-11. The grading rubric scores ML 0-3 points.
To score 3 ("outstanding, far beyond the level of this course"), the
project must demonstrate mastery of everything taught AND go beyond it.

### What the course teaches (mandatory baseline)

These patterns come from lectures 10/11, notebooks 10-0 through 11,
and assignments 10-11. All must be present in the project:

1. **Train/test split** -- `train_test_split(stratify=..., random_state=...)`
2. **Data scaling** -- `MinMaxScaler`, `StandardScaler`, or `RobustScaler`
   (fit on train, transform train+val+test)
3. **5+ classifier comparison** -- at minimum:
   - `KNeighborsClassifier`
   - `SVC` (or `LinearSVC`)
   - `GaussianNB`
   - `LogisticRegression`
   - `MLPClassifier`
   - `DummyClassifier` (baseline: `most_frequent` + `stratified`)
4. **Evaluation metrics** -- `classification_report` (precision, recall,
   F1, macro/weighted avg), `ConfusionMatrixDisplay.from_predictions`,
   `accuracy_score`
5. **Cross-validation** -- `KFold` + `cross_val_score` (report mean +
   std accuracy)
6. **Hyperparameter tuning** -- at least vary k in KNN, show accuracy vs
   hyperparameter plot

### What goes beyond the course (for score 3)

Our project adds these elements not covered in the lectures:

- **TF-IDF + TruncatedSVD** on keyword/director/actor features (notebook
  10-2 covers TF-IDF on text, but SVD dimensionality reduction is new)
- **Content-based recommendation scoring** with 9 weighted similarity
  signals (not taught in course)
- **Dynamic weight adjustment** by rating count (cold start handling)
- **Pre-trained transformer** for emotion classification on movie text
  (j-hartmann/emotion-english-distilroberta-base)
- **Bayesian average** quality scoring (not taught)
- **Offline pipeline** processing 1.17M movies into .npy arrays

### Concrete ML evaluation deliverable

A dedicated evaluation section (in the app's Statistics page or a
separate notebook) must show:

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
results = []
for name, clf in estimators.items():
    clf.fit(X_train_scaled, y_train)
    y_pred = clf.predict(X_test_scaled)
    results.append({
        "Classifier": name,
        "Accuracy": accuracy_score(y_test, y_pred),
        "Precision": precision_score(y_test, y_pred, average="macro"),
        "Recall": recall_score(y_test, y_pred, average="macro"),
        "F1": f1_score(y_test, y_pred, average="macro"),
    })
results_df = pd.DataFrame(results)

# 4. Best model: confusion matrix + classification_report
best_clf = ...  # select from results_df
ConfusionMatrixDisplay.from_predictions(y_test, y_pred)
print(classification_report(y_test, y_pred))

# 5. Cross-validation
kfold = KFold(n_splits=10, shuffle=True, random_state=42)
scores = cross_val_score(best_clf, X_scaled, y, cv=kfold)
print(f"Mean: {scores.mean():.2%}, Std: {scores.std():.2%}")
```

The classification task: given a user's feature profile and a movie's
feature vector, predict whether the user would rate the movie as
"liked" (rating >= 60) or "disliked" (rating < 60). This is a binary
classification problem.

---

## Architecture

```
data/tmdb.db (8.2 GB, offline only)
    |
    |  pipeline/01_extract_features.py
    |  pipeline/02_predict_moods.py
    |  pipeline/03_quality_scores.py
    |  pipeline/04_build_index.py
    |
    v
model/ (~3 GB, shipped to production)
    keyword_svd_vectors.npy     1.17M x 200   float32
    director_svd_vectors.npy    1.17M x 200   float32
    actor_svd_vectors.npy       1.17M x 200   float32
    genre_vectors.npy           1.17M x 19    float32
    decade_vectors.npy          1.17M x 15    float32
    language_vectors.npy        1.17M x 20    float32
    runtime_normalized.npy      1.17M x 1     float32
    mood_scores.npy             1.17M x 7     float32
    quality_scores.npy          1.17M x 1     float32
    movie_id_index.json         1.17M entries
    genre_mood_map.json         19 entries
    keyword_mood_map.json       ~70K entries
    svd_models/
      keyword_svd.pkl
      director_svd.pkl
      actor_svd.pkl
```

The 8.2 GB database is never queried at runtime. Only the model files
are loaded into memory for scoring.

---

## Stage 1: Feature Extraction

**Script:** `pipeline/01_extract_features.py`

**Input:** `data/tmdb.db`

Extracts feature matrices from the TMDB database and reduces
high-dimensional sparse features via SVD.

| Feature | Raw Dimensions | Reduced | DB Source |
|---|---|---|---|
| Keyword TF-IDF | 1.17M x 70,779 | 1.17M x 200 (SVD) | `movie_keywords` + `keywords` |
| Genre onehot | 1.17M x 19 | No reduction | `movie_genres` + `genres` |
| Director onehot | 1.17M x ~170K | 1.17M x 200 (SVD) | `movie_crew` WHERE `job = 'Director'` |
| Actor onehot | 1.17M x ~4M | 1.17M x 200 (SVD) | `movie_cast` WHERE `cast_order < 5` |
| Decade onehot | 1.17M x 15 | No reduction | `movies.release_date` -> decade bins (1900s-2020s) |
| Language onehot | 1.17M x 20 | No reduction | `movies.original_language` top-20 by count |
| Runtime normalized | 1.17M x 1 | No reduction | `movies.runtime / 360.0` |

**SVD details:**

- TruncatedSVD with 200 components
- Keywords use TF-IDF weighting before SVD
- Directors and actors use binary onehot (present/absent) before SVD
- SVD models are saved as `.pkl` for transforming new movies later

**Output:**

```
model/keyword_svd_vectors.npy
model/director_svd_vectors.npy
model/actor_svd_vectors.npy
model/genre_vectors.npy
model/decade_vectors.npy
model/language_vectors.npy
model/runtime_normalized.npy
model/movie_id_index.json
model/svd_models/keyword_svd.pkl
model/svd_models/director_svd.pkl
model/svd_models/actor_svd.pkl
```

---

## Stage 2: Mood Score Prediction

**Script:** `pipeline/02_predict_moods.py`

**Input:** `data/tmdb.db` + `model/genre_mood_map.json` +
`model/keyword_mood_map.json`

For each movie, predicts 7 mood probabilities:
happy, interested, surprised, sad, disgusted, afraid, angry.

---

### Signal 1: Genre -> Mood Mapping

19 manual rules mapping each genre to mood weights. Weights are
independent scores (not normalized to 1.0) representing the strength
of each mood signal for the genre. Canonical source:
`model/genre_mood_map.json`.

```
Action          -> {interested: 0.5, afraid: 0.3}
Adventure       -> {happy: 0.4, interested: 0.4, surprised: 0.3}
Animation       -> {happy: 0.5, sad: 0.2, interested: 0.2}
Comedy          -> {happy: 0.8, surprised: 0.2}
Crime           -> {angry: 0.4, interested: 0.4, afraid: 0.2}
Documentary     -> {interested: 0.6, sad: 0.2, angry: 0.1}
Drama           -> {sad: 0.5, interested: 0.4}
Family          -> {happy: 0.5, sad: 0.2}
Fantasy         -> {interested: 0.5, surprised: 0.3, happy: 0.2}
History         -> {interested: 0.6, sad: 0.3, angry: 0.1}
Horror          -> {afraid: 0.7, disgusted: 0.3}
Music           -> {happy: 0.6, interested: 0.3, sad: 0.1}
Mystery         -> {interested: 0.5, surprised: 0.4, afraid: 0.2}
Romance         -> {happy: 0.6, sad: 0.3}
Science Fiction -> {interested: 0.5, surprised: 0.3, afraid: 0.2}
TV Movie        -> {}
Thriller        -> {afraid: 0.5, interested: 0.4, surprised: 0.2}
War             -> {angry: 0.5, sad: 0.5, afraid: 0.2}
Western         -> {interested: 0.4, happy: 0.2, angry: 0.2}
```

For multi-genre movies, mood scores are averaged across genres.

Stored in: `model/genre_mood_map.json`

---

### Signal 2: Keyword -> Mood Mapping (Supervised Pipeline)

TMDB has 70K+ unique keywords. Manual tagging is infeasible. Instead,
a two-stage supervised pipeline produces the mapping.

**Stage A: Labeled seed dataset (complete)**

5,000 most frequent TMDB keywords labeled by Claude agent.
Source: `data/tmdb-keyword-frequencies_labeled_top5000.tsv`

| Assignment Type | Count | Description |
|---|---|---|
| single | 1,697 → 1,049 after review | Exactly one mood assigned |
| multi | 2,047 → 1,634 after review | Multiple moods assigned |
| none | 1,256 → 2,317 after review | Not mood-relevant (metadata, format, identity tags) |

Post-review counts reflect ~666 corrections (see [MOOD.md](MOOD.md) Stage 2).
The single-label subset (1,049) is the actual training set for Stage B.

Single-label class distribution:

| Mood | Count |
|---|---|
| Interested | 910 |
| Happy | 363 |
| Afraid | 177 |
| Sad | 153 |
| Angry | 51 |
| Disgusted | 26 |
| Surprised | 17 |

Imbalance note: Angry, Disgusted, Surprised are inherently rare as
single-label assignments. These moods appear primarily in multi-label
form (Angry: 537, Disgusted: 236, Surprised: 254).

**Stage B: Supervised classification (course-compliant)**

Training uses the single-label subset only (1,049 keywords after
manual review). This gives a methodologically clean 7-class
classification problem.

1. **Features:** EmbeddingGemma-300M sentence embeddings (256-dim)
   per keyword. Model cached at
   `~/.cache/macmini/huggingface/hub/models--google--embeddinggemma-300m`
2. **Train/test split:** `train_test_split(stratify=y, random_state=42)`
3. **Scaling:** `RobustScaler` on embedding vectors (fit on train only)
4. **Classifier comparison:** KNN, SVC, GaussianNB, LogisticRegression,
   MLPClassifier, DummyClassifier baselines
5. **Evaluation:** `classification_report`, confusion matrix, macro-F1
   (careful interpretation due to class imbalance)
6. **Cross-validation:** `KFold` + `cross_val_score`
7. **Hyperparameter tuning:** k in KNN, etc.
8. **Model selection:** Best classifier chosen by evaluation metrics
9. **Full inference:** Best model applied to all remaining 70K+
   unlabeled keywords

This gives a reproducible, evaluable, course-compliant classification
pipeline rather than an opaque heuristic. It also serves as a second
ML showcase alongside the user preference classification.

**Output:** `model/keyword_mood_map.json` (70K+ entries, predicted
mood scores per keyword)

Stored in: `model/keyword_mood_map.json`

---

### Signal 3: Emotion Classifier on Overview Text

Pre-trained transformer model applied to all movie overviews.

- **Model:** `j-hartmann/emotion-english-distilroberta-base`
- **Input:** `movies.overview` + `movies.tagline` (concatenated)
- **Output:** `{anger, disgust, fear, joy, sadness, surprise}` (6 classes)
- **Mapping to 7 moods:**
  - `joy` -> `happy`
  - `anger` -> `angry`
  - `disgust` -> `disgusted`
  - `fear` -> `afraid`
  - `sadness` -> `sad`
  - `surprise` -> `surprised`
  - `interested` derived from low max-confidence (classifier is
    uncertain = the movie is thought-provoking rather than emotionally
    extreme)

~995K movies have non-empty overviews. The remaining ~179K get mood
scores only from genre and keyword signals.

---

### Signal 4: Emotion Classifier on Reviews

Same classifier applied to `movie_reviews.content`. Only 38,535 movies
(3.3%) have reviews. For those, all review texts are concatenated (or
individual emotions are averaged).

Reviews are the most authentic mood signal because viewers describe
what they actually felt: "had me on the edge of my seat" (surprised/
afraid), "couldn't stop laughing" (happy).

---

### Signal Combination

Dynamic weighting based on availability:

```
If reviews available:
    0.50 * reviews_emotion
  + 0.20 * overview_emotion
  + 0.20 * genre_mood
  + 0.10 * keyword_mood

If no reviews (96.7% of movies):
    0.50 * overview_emotion
  + 0.30 * genre_mood
  + 0.20 * keyword_mood

If no overview either (~15%):
    0.60 * genre_mood
  + 0.40 * keyword_mood
```

Weights always normalize to 1.0. When a signal is unavailable, its
weight redistributes to the remaining signals.

**Output:** `model/mood_scores.npy` (1.17M x 7)

---

## Stage 3: Quality Scores

**Script:** `pipeline/03_quality_scores.py`

**Input:** `data/tmdb.db` (`movies.vote_average`, `movies.vote_count`)

Bayesian average to prevent movies with very few votes from ranking
unfairly high:

```
m = median(all_vote_counts)       # ~14 for TMDB
C = mean(all_vote_averages)       # ~6.0 for TMDB
quality = (v * R + m * C) / (v + m)
```

Where `v` = vote_count, `R` = vote_average.

A movie with 1 vote and 10.0 average gets pulled toward 6.0. A movie
with 10,000 votes stays close to its actual average.

Normalized to [0, 1] range.

**Output:** `model/quality_scores.npy` (1.17M x 1)

---

## Stage 4: Build Index

**Script:** `pipeline/04_build_index.py`

Saves the final mappings:

- `model/movie_id_index.json` -- bidirectional mapping between
  `movie_id` (TMDB integer ID) and row index (position in `.npy`
  arrays). Required to look up vectors for movies returned by the
  TMDB API.
- `model/genre_mood_map.json` -- 19 genre -> mood rules
- `model/keyword_mood_map.json` -- ~70K keyword -> mood predictions
- `model/svd_models/*.pkl` -- saved SVD transformers for future use

---

## Running the Pipeline

```bash
# Full pipeline (takes several hours for mood prediction on 1.17M movies)
python3 pipeline/01_extract_features.py --db data/tmdb.db --output model/
python3 pipeline/02_predict_moods.py --db data/tmdb.db --output model/
python3 pipeline/03_quality_scores.py --db data/tmdb.db --output model/
python3 pipeline/04_build_index.py --output model/
```

Each stage is idempotent and can be re-run independently.

---

## Dependencies

| Package | Purpose |
|---|---|
| `numpy` | Array operations, `.npy` storage |
| `scipy` | Sparse matrices for TF-IDF, SVD |
| `scikit-learn` | TruncatedSVD, TfidfTransformer |
| `transformers` | Emotion classifier (Stage 2) |
| `torch` | Backend for transformers |
| `tqdm` | Progress bars |

---

## Memory Requirements

| Stage | Peak RAM |
|---|---|
| Feature extraction (keyword TF-IDF) | ~8 GB (sparse matrix) |
| SVD reduction | ~4 GB |
| Emotion classifier (batched) | ~2 GB (GPU) or ~4 GB (CPU) |
| Final .npy arrays in memory | ~3 GB |

---

## Online Pipeline (per request at runtime)

The online pipeline scores candidate movies for a user. It runs on
every Discover request when sort="Personalized Score".

**Files:**

| File | Responsibility |
|---|---|
| `app/utils/scoring.py` | Scoring formula, dynamic weights, cosine similarity, batch scoring |
| `app/utils/filters.py` | TMDB API parameter builder from UI state, local mood filter |
| `app/utils/user_profile.py` | User profile computation from ratings (weighted avg of .npy vectors) |

**Data flow:**

```
User clicks "Discover" with filters
    |
    v
1. filters.py: Build TMDB API params from UI state
   GET /3/discover/movie?with_genres=...&certification=...&...
   -> 100-500 candidate movie IDs
    |
    v
2. filters.py: Local mood filter (if mood selected)
   mood_scores.npy[movie_id_index[id]] > threshold
   -> Filter down to mood-matching candidates
    |
    v
3. user_profile.py: Build user profile (cached after each rating)
   For each rated movie: look up .npy vectors, weight by rating
   -> user_keyword_vec, user_director_vec, user_actor_vec,
      user_decade_vec, user_language_vec, user_runtime_pref,
      user_implicit_mood, user_contra_vec
    |
    v
4. scoring.py: Batch-score all candidates (numpy vectorized, ~50ms)
   final_score = weighted sum of 9 similarity components
   Weights shift by rating count (cold start -> quality-heavy,
   50+ ratings -> personalization-heavy)
   -> Sorted top-20
    |
    v
5. TMDB API: Fetch details for top-20 (parallel)
   GET /3/movie/{id}?append_to_response=watch/providers,videos,
       release_dates,credits
```

---

## Files To Create

| File | Content | Priority |
|---|---|---|
| `app/utils/scoring.py` | Scoring formula, dynamic weights, cosine similarity, batch scoring | High |
| `app/utils/filters.py` | TMDB API parameter builder from UI state, local mood filter | High |
| `app/utils/user_profile.py` | User profile computation from ratings (weighted avg of .npy vectors) | High |
| `pipeline/01_extract_features.py` | Stage 1: tmdb.db -> SVD/onehot -> .npy | High (prerequisite) |
| `pipeline/02_predict_moods.py` | Stage 2: genre/keyword mapping + emotion classifier -> mood_scores.npy | High |
| `pipeline/03_quality_scores.py` | Stage 3: Bayesian average -> quality_scores.npy | Medium |
| `pipeline/04_build_index.py` | Stage 4: movie_id_index.json + SVD .pkl saving | Medium |
| `model/genre_mood_map.json` | 19 genre -> mood rules (manual) | High |
| `model/keyword_mood_map.json` | 70K+ keyword -> mood predictions (from supervised pipeline) | Medium |
| `pipeline/keyword_mood_classifier.py` | Stage A+B: label seed data, train classifier, infer full keyword set | Medium |
| `app/utils/ml_eval.py` | Shared ML evaluation logic (classifiers, metrics, CV) for Statistics page + notebook | High |
| `notebooks/ml_evaluation.ipynb` | Detailed ML evaluation notebook (academic, narrative) | Medium |

---

## ML Evaluation (Requirement 5 deliverable)

The ML evaluation proves that the personalized scoring model works
better than random chance. It follows the exact workflow taught in
the course (lectures 10-11, assignments 10-11).

### Classification Problem Definition

- **Task:** Binary classification -- predict whether a user would rate
  a movie as "liked" (>= 60/100) or "disliked" (< 60/100)
- **Features (X):** For each (user, movie) pair, compute the 9 scoring
  components as a feature vector:
  `[keyword_sim, mood_match, director_sim, actor_sim, decade_sim,
   language_sim, runtime_sim, quality_score, contra_penalty]`
- **Labels (y):** Binary, derived from actual user ratings
  (`1` = liked, `0` = disliked)
- **Data source:** All entries in `user_ratings` table

### Evaluation Workflow

1. **Data split:** `train_test_split(test_size=0.2, stratify=y,
   random_state=42)` -- stratified to preserve liked/disliked ratio

2. **Scaling:** `RobustScaler().fit(X_train)` then transform both
   train and test. RobustScaler chosen because similarity scores may
   have outliers.

3. **Classifier comparison (5+ classifiers):**

   | Classifier | sklearn Class | Key Params |
   |---|---|---|
   | KNN | `KNeighborsClassifier` | `n_neighbors=5` |
   | SVM | `SVC` | `gamma="scale"` |
   | Naive Bayes | `GaussianNB` | -- |
   | Logistic Regression | `LogisticRegression` | `max_iter=1000` |
   | Neural Network | `MLPClassifier` | `hidden_layer_sizes=[64, 64]` |
   | Baseline (frequent) | `DummyClassifier` | `strategy="most_frequent"` |
   | Baseline (stratified) | `DummyClassifier` | `strategy="stratified"` |

4. **Metrics per classifier (DataFrame):**
   - Accuracy, Precision (macro), Recall (macro), F1 (macro)
   - Compare scaled vs unscaled (following assignment-11 pattern)

5. **Best classifier deep dive:**
   - `ConfusionMatrixDisplay.from_predictions(y_test, y_pred)`
   - `classification_report(y_test, y_pred)`

6. **Cross-validation:**
   - `KFold(n_splits=10, shuffle=True, random_state=42)`
   - `cross_val_score(best_clf, X, y, cv=kfold)`
   - Report mean accuracy +/- std

7. **Hyperparameter tuning (optional):**
   - KNN: vary k from 1 to 20, plot accuracy vs k with error bars
   - Select optimal k

### Two Classification Problems

The project demonstrates ML with two distinct classification tasks:

1. **User preference classification:** Predict liked/disliked from 9
   scoring-component feature vectors (described above)
2. **Keyword-to-mood classification:** Predict mood category from
   sentence embeddings of TMDB keywords (see Stage B in Signal 2)

Both follow the same course-compliant evaluation workflow.

### Where to Show This

Both locations, with shared logic:

- **Shared utility:** `app/utils/ml_eval.py` contains all evaluation
  logic (`evaluate_classifiers()`, `best_model_report()`,
  `run_cross_validation()`)
- **Statistics page** (compact, video-friendly): "Run ML Evaluation"
  button, classifier comparison table, best model KPIs (accuracy + F1),
  confusion matrix, classification report, cross-validation score
- **Jupyter notebook** `notebooks/ml_evaluation.ipynb` (academic,
  narrative): problem definition, feature engineering explanation,
  data distribution plots, all 7 classifiers with commentary, scaled
  vs unscaled comparison, KNN hyperparameter tuning (k=1..20 plot),
  discussion/interpretation

Separation principle: notebook shows the "why", Statistics page shows
the result. No duplicated code -- both call `ml_eval.py`.

### Cold Start Handling

With 0 ratings, the classifier cannot run. The scoring falls back to:
- Quality score (Bayesian average) + mood match (if selected)
- No personalization signals until >= 1 rating
- Dynamic weight table shifts from quality-heavy to
  personalization-heavy as ratings accumulate (see MIGRATION.md)
