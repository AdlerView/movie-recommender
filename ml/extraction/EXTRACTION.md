# EXTRACTION

Offline feature extraction from `tmdb.sqlite` into `.npy` arrays. No ML models — pure data transformation. This directory also serves as the entry point for the full offline pipeline (4 stages across `ml/extraction/` and `ml/classification/`).

---

## Pipeline Architecture

```
data/input/tmdb.sqlite (7.7 GB, offline only)
    |
    |  ml/extraction/01_extract_features.py
    |  ml/classification/02_predict_moods.py
    |  ml/extraction/03_quality_scores.py
    |  ml/extraction/04_build_index.py
    |
    v
data/output/ (~3 GB, shipped to production)
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
    keyword_mood_map.json       ~70K entries
    keyword_svd.pkl
    director_svd.pkl
    actor_svd.pkl
```

The 7.7 GB database is never queried at runtime. Only the model files
are loaded into memory for scoring.

---

## Stage 1: Feature Extraction

**Script:** `01_extract_features.py`

**Input:** `data/input/tmdb.sqlite`

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

- TruncatedSVD with 200 components (pragmatic default from LSA
  literature, configurable via `--svd-components`). Observed explained
  variance: keywords 33.7%, directors 2.8%, actors 1.7%. Low
  director/actor values reflect extreme sparsity (most people appear
  in 1-2 films), not a poor component count.
- Keywords use TF-IDF weighting before SVD (same math as
  TfidfVectorizer in course Notebook 10-2)
- Directors and actors use binary onehot (present/absent) before SVD
- SVD models saved as `.pkl` for transforming new movies later

**Output:** 7 `.npy` arrays + 3 `.pkl` SVD models + `movie_id_index.json`

---

## Stage 3: Quality Scores

**Script:** `03_quality_scores.py`

**Input:** `data/input/tmdb.sqlite` (`movies.vote_average`, `movies.vote_count`)

Bayesian average to prevent movies with very few votes from ranking
unfairly high:

```
m = median(all_vote_counts)       # ~14 for TMDB
C = mean(all_vote_averages)       # ~6.0 for TMDB
quality = (v * R + m * C) / (v + m)
```

Where `v` = vote_count, `R` = vote_average. A movie with 1 vote and
10.0 average gets pulled toward 6.0. Normalized to [0, 1] range.

**Output:** `data/output/quality_scores.npy` (1.17M x 1)

---

## Stage 4: Build Index

**Script:** `04_build_index.py`

Saves the final mappings:

- `data/output/movie_id_index.json` — bidirectional mapping between
  `movie_id` (TMDB integer ID) and row index (position in `.npy`
  arrays). Required to look up vectors for movies returned by the
  TMDB API.

Verifies all 14 pipeline outputs exist and have consistent row counts.

---

## Running the Pipeline

```bash
# Full pipeline (takes several hours for mood prediction)
python3 ml/extraction/01_extract_features.py --db data/input/tmdb.sqlite --output data/output/
python3 ml/classification/02_predict_moods.py --db data/input/tmdb.sqlite --output data/output/
python3 ml/extraction/03_quality_scores.py --db data/input/tmdb.sqlite --output data/output/
python3 ml/extraction/04_build_index.py --output data/output/
```

Run order: `01` + `03` (parallel) → `keyword_mood_classifier` → `02` → `04`.
Each stage is idempotent and can be re-run independently.

---

## Files Status

| File | Status | Content |
|---|---|---|
| `ml/extraction/01_extract_features.py` | DONE | Stage 1: tmdb.sqlite -> SVD/onehot -> .npy |
| `ml/classification/02_predict_moods.py` | DONE | Stage 2: genre/keyword/emotion -> mood_scores.npy |
| `ml/extraction/03_quality_scores.py` | DONE | Stage 3: Bayesian average -> quality_scores.npy |
| `ml/extraction/04_build_index.py` | DONE | Stage 4: movie_id_index.json + verification |
| `ml/classification/keyword_mood_classifier.py` | DONE | Keyword-to-mood: train classifier, infer 70K+ |
| `ml/scoring/scoring.py` | DONE | Scoring formula, dynamic weights, cosine similarity |
| `ml/scoring/mood_filter.py` | DONE | Local mood filter against mood_scores.npy |
| `ml/scoring/user_profile.py` | DONE | User profile computation from ratings |
| `ml/evaluation/ml_eval.py` | DONE | Shared ML evaluation logic |
| `ml/evaluation/ml_evaluation.ipynb` | PENDING | Academic narrative notebook |

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
