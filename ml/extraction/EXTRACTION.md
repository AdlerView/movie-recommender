# EXTRACTION

Offline feature extraction from `tmdb.sqlite` into `.npy` arrays. No ML models — pure data transformation. This directory also serves as the entry point for the full offline pipeline (4 stages across `ml/extraction/` and `ml/classification/`).

---

## Pipeline Architecture

```
data/input/tmdb.sqlite (7.7 GB, offline only)
    |
    |  ml/extraction/extract_features.py
    |  ml/extraction/moods.py
    |  ml/extraction/quality_scores.py
    |  ml/extraction/index.py
    |  ml/extraction/verify.py
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

**Script:** `extract_features.py`

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
- Keywords use TF-IDF weighting before SVD
- Directors and actors use binary onehot (present/absent) before SVD
- SVD models saved as `.pkl` for transforming new movies later

**Output:** 7 `.npy` arrays + 3 `.pkl` SVD models + `movie_id_index.json`

---

## Stage 3: Quality Scores

**Script:** `quality_scores.py`

Bayesian average quality score, normalized to [0, 1]. Formula and behavior: see SCORING.md (Quality Score section).

**Output:** `data/output/quality_scores.npy` (1.17M x 1)

---

## Stage 4a: Build Index

**Script:** `index.py`

Saves `data/output/movie_id_index.json` — bidirectional mapping between `movie_id` (TMDB integer ID) and row index (position in `.npy` arrays). Required to look up vectors for movies returned by the TMDB API.

---

## Stage 4b: Verify Pipeline

**Script:** `verify.py`

Verifies all 14 pipeline outputs exist and have consistent row counts against movie_id_index.json. No database access needed.

---

## Running the Pipeline

```bash
# Full pipeline (takes several hours for mood prediction)
python3 ml/extraction/extract_features.py --db data/input/tmdb.sqlite --output data/output/
python3 ml/extraction/moods.py --db data/input/tmdb.sqlite --output data/output/
python3 ml/extraction/quality_scores.py --db data/input/tmdb.sqlite --output data/output/
python3 ml/extraction/index.py --db data/input/tmdb.sqlite --output data/output/
python3 ml/extraction/verify.py --output data/output/
```

Run order: `extract_features` + `quality_scores` (parallel) → `keyword_mood_classifier` → `moods` → `index` → `verify`.
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
