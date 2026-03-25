# ML-PIPELINE.md

Offline ML pipeline that transforms the TMDB SQLite database into
precomputed model files used at runtime for personalized scoring.

**Created:** 2026-03-26
**Updated:** 2026-03-26

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
    keyword_mood_map.json       ~500 entries
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

19 manual rules mapping each genre to mood weights.

```
Action      -> {afraid: 0.2, surprised: 0.3, interested: 0.3}
Adventure   -> {happy: 0.4, interested: 0.4, surprised: 0.3}
Animation   -> {happy: 0.6, interested: 0.2}
Comedy      -> {happy: 0.8, surprised: 0.2}
Crime       -> {angry: 0.4, interested: 0.4, afraid: 0.2}
Documentary -> {interested: 0.8}
Drama       -> {sad: 0.5, interested: 0.4}
Family      -> {happy: 0.7}
Fantasy     -> {interested: 0.5, surprised: 0.3, happy: 0.2}
History     -> {interested: 0.6, sad: 0.3}
Horror      -> {afraid: 0.8, disgusted: 0.3, surprised: 0.2}
Music       -> {happy: 0.6, interested: 0.3}
Mystery     -> {interested: 0.5, surprised: 0.4, afraid: 0.2}
Romance     -> {happy: 0.6, sad: 0.3}
Science Fiction -> {interested: 0.5, surprised: 0.3, afraid: 0.2}
TV Movie    -> {interested: 0.3}
Thriller    -> {surprised: 0.5, afraid: 0.4, interested: 0.3}
War         -> {angry: 0.5, sad: 0.5, afraid: 0.2}
Western     -> {interested: 0.3, angry: 0.2}
```

For multi-genre movies, mood scores are averaged across genres.

Stored in: `model/genre_mood_map.json`

---

### Signal 2: Keyword -> Mood Mapping

Top-500 keywords by movie count, manually tagged with mood weights.

```
"revenge"       -> {angry: 0.8}
"murder"        -> {afraid: 0.5, disgusted: 0.3}
"love"          -> {happy: 0.7}
"tragedy"       -> {sad: 0.9}
"plot twist"    -> {surprised: 0.9}
"serial killer" -> {afraid: 0.7, disgusted: 0.5}
"friendship"    -> {happy: 0.6}
"war"           -> {angry: 0.5, sad: 0.4}
"dystopia"      -> {afraid: 0.4, angry: 0.3}
...
```

Keywords not in the top-500 are ignored (long tail, most appear in
fewer than 5 movies).

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
- `model/keyword_mood_map.json` -- ~500 keyword -> mood rules
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
