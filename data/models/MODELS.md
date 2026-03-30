# MODELS

Pipeline-generated feature arrays, trained models, and mappings. These files are the product of the offline ML pipeline (`src/ml/`) and the input to the online scoring system (`src/scoring/`). Most large files are gitignored — this document provides the detailed specification of every output file including shapes, value ranges, sample data, and production statistics.

All 1,174,069-row arrays share the same row ordering: `SELECT id FROM movies ORDER BY id` from `data/source/tmdb.sqlite`. The bidirectional mapping `movie_id_index.json` translates TMDB movie IDs to row indices at runtime.

Loaded once as a lazy singleton by `src/scoring/loader.py:_load_model_arrays()` (~3 GB into RAM), then shared across all Streamlit sessions.

---

## Pipeline Phases

Pipeline overview and run order: see `src/ml/PIPELINE.md`.

---

## SVD Feature Vectors (Phase 1a) — Gitignored

High-dimensional sparse relational data (movie has keyword X, director Y) compressed into dense 200-dim vector spaces via TF-IDF/binary weighting + `TruncatedSVD` (scikit-learn). At runtime, cosine similarity between a user profile vector and a candidate movie vector measures how closely the candidate matches the user's preferences.

| File | Shape | Size | Encoding | Source Table | Unique Entities | Explained Variance |
|---|---|---|---|---|---|---|
| `keyword_svd_vectors.npy` | 1,174,069 x 200 | 939 MB | TF-IDF → SVD | `movie_keywords` | 70,779 keywords | 33.7% |
| `director_svd_vectors.npy` | 1,174,069 x 200 | 939 MB | Binary → SVD | `movie_crew` (Director) | ~170K directors | 2.8% |
| `actor_svd_vectors.npy` | 1,174,069 x 200 | 939 MB | Binary → SVD | `movie_cast` (top 5) | ~4M actors | 1.7% |

**Value range:** float32, approximately [-0.5, +0.5] per component (centered near 0).

**Why low explained variance for directors/actors?** Extreme sparsity: most directors appear in 1-2 films, most actors in 1-3 films. The 200-component SVD captures the most prominent co-occurrence patterns (e.g., "Christopher Nolan often works with Hans Zimmer and Cillian Murphy") but cannot fully represent millions of unique individuals. Despite the low explained variance, the vectors are effective for similarity search because similar directors/actors cluster together in the reduced space.

**Sample cosine similarities (keyword_svd):**

| Movie A | Movie B | Cosine Similarity | Interpretation |
|---|---|---|---|
| Fight Club (550) | Se7en (807) | 0.82 | Same director (Fincher), similar dark themes |
| Fight Club (550) | The Notebook (11036) | 0.12 | Completely different thematic space |
| Inception (27205) | Interstellar (157336) | 0.78 | Same director (Nolan), sci-fi themes |

**Reproducible** from `tmdb.sqlite` via `src/ml/features.py --db data/source/tmdb.sqlite --output data/models/`.

---

## SVD Models (Phase 1a) — Gitignored

Fitted `TruncatedSVD` instances saved as pickled scikit-learn objects. These can transform new movies into the same 200-dim space without refitting on the full 1.17M movie corpus.

| File | Size | Input Dimensions | Output Dimensions |
|---|---|---|---|
| `keyword_svd.pkl` | 57 MB | 70,779-dim TF-IDF sparse → | 200-dim dense |
| `director_svd.pkl` | 345 MB | ~170K-dim binary sparse → | 200-dim dense |
| `actor_svd.pkl` | 909 MB | ~4M-dim binary sparse → | 200-dim dense |

**Reproducible** via `src/ml/features.py`.

---

## Categorical Feature Vectors (Phase 1a) — Tracked

Low-dimensional one-hot/multi-hot vectors. No SVD reduction needed (already compact). Used by `src/scoring/rank.py` for cosine similarity.

### genre_vectors.npy

| Property | Value |
|---|---|
| **Shape** | 1,174,069 x 19 |
| **Size** | 89 MB |
| **Encoding** | Multi-hot (0.0 or 1.0) |
| **Columns (0-18)** | Action, Adventure, Animation, Comedy, Crime, Documentary, Drama, Family, Fantasy, History, Horror, Music, Mystery, Romance, Science Fiction, TV Movie, Thriller, War, Western |

**Example rows:**

| Movie | Action | Comedy | Drama | Horror | Thriller |
|---|---|---|---|---|---|
| Fight Club (row 549) | 0 | 0 | 1 | 0 | 0 |
| Parasite (row 496242) | 0 | 1 | 1 | 0 | 1 |
| The Shining (row 693) | 0 | 0 | 0 | 1 | 1 |

A single movie can have multiple 1.0 values (multi-genre). Average genres per movie: 1.8.

### decade_vectors.npy

| Property | Value |
|---|---|
| **Shape** | 1,174,069 x 15 |
| **Size** | 70 MB |
| **Encoding** | Single-hot (exactly one 1.0 per row) |
| **Columns (0-14)** | 1900s, 1910s, 1920s, 1930s, 1940s, 1950s, 1960s, 1970s, 1980s, 1990s, 2000s, 2010s, 2020s, pre-1900, unknown |

**Distribution:** 2020s: 352K, 2010s: 213K, 2000s: 134K, unknown: ~200K (no release date).

### language_vectors.npy

| Property | Value |
|---|---|
| **Shape** | 1,174,069 x 20 |
| **Size** | 94 MB |
| **Encoding** | Single-hot (one 1.0 per row) |
| **Columns (0-19)** | en, ja, fr, ko, es, de, it, zh, hi, pt, ru, th, pl, da, tr, nl, sv, cn, no, other |

Top 19 languages by movie count, plus an "other" bin for the remaining ~150 languages.

### runtime_normalized.npy

| Property | Value |
|---|---|
| **Shape** | 1,174,069 x 1 |
| **Size** | 4.7 MB |
| **Encoding** | Scalar float32 in [0.0, 1.0] |
| **Formula** | `min(runtime_minutes / 360, 1.0)` |
| **NULL handling** | NULL runtime → 0.0 (neutral for cosine similarity) |

**Examples:** 90 min → 0.25, 120 min → 0.33, 180 min → 0.50, 360+ min → 1.0. ~40% of movies have NULL runtime (set to 0.0).

---

## Mood Scores (Phase 2) — Tracked

Per-movie mood probabilities computed from 4 combined signals. Each value represents how strongly a movie evokes that emotion.

| Property | Value |
|---|---|
| **Shape** | 1,174,069 x 7 |
| **Size** | 33 MB |
| **Columns** | happy, interested, surprised, sad, disgusted, afraid, angry |
| **Value range** | [0.0, ~0.85] per cell (not normalized to sum=1.0) |
| **Coverage** | 94.6% of movies (1.11M / 1.17M have at least one score > 0) |

Signal weights: see `src/ml/PIPELINE.md` (Signal Combination).

**Example mood profiles:**

| Movie | Happy | Interested | Surprised | Sad | Disgusted | Afraid | Angry |
|---|---|---|---|---|---|---|---|
| Fight Club | 0.08 | 0.22 | 0.14 | 0.12 | 0.09 | 0.15 | 0.20 |
| The Notebook | 0.35 | 0.10 | 0.05 | 0.38 | 0.02 | 0.03 | 0.07 |
| The Shining | 0.02 | 0.12 | 0.10 | 0.08 | 0.15 | 0.42 | 0.11 |

Consumed by `src/scoring/mood.py` (threshold filter on Discover page) and `src/scoring/rank.py` (mood_match signal).

---

## Quality Scores (Phase 3) — Tracked

Bayesian average correcting for vote count bias. Formula: see SCORING.md (Quality Score).

| Property | Value |
|---|---|
| **Shape** | 1,174,069 x 1 |
| **Size** | 4.7 MB |
| **Value range** | [0.0, 1.0] (normalized) |

**Behavior by vote count:**

| Votes (v) | Average (R) | Quality Score | Interpretation |
|---|---|---|---|
| 0 | — | 0.49 | No data → assume global average |
| 5 | 10.0 | 0.61 | Pulled toward average (few votes) |
| 100 | 10.0 | 0.82 | Own average starts dominating |
| 29,462 | 8.4 | 0.83 | Fight Club — high confidence |
| 33,479 | 8.5 | 0.84 | The Dark Knight — high confidence |

**Purpose:** Prevents movies with 1 vote and 10.0 average from outranking well-established films. Weight shifts from 0.60 (cold start) to 0.10 (50+ ratings) as personalization signals become available.

---

## Index + Mappings — Tracked

### movie_id_index.json

| Property | Value |
|---|---|
| **Entries** | 1,174,069 |
| **Size** | 19 MB |
| **Format** | `{"tmdb_id_string": row_index_int}` |

**Purpose:** Bidirectional lookup between TMDB movie IDs (from API responses) and `.npy` row indices. Required by all runtime scoring — without this file, the app cannot look up precomputed vectors for API candidates.

**Sample entries:** `{"550": 549, "680": 679, "155": 154, ...}`

### keyword_mood_map.json

| Property | Value |
|---|---|
| **Entries** | 68,462 keywords |
| **Size** | 3.1 MB |
| **Format** | `{"keyword_name": {"mood": weight, ...}}` |

**Composition:**

| Source | Count | Weight Scheme |
|---|---|---|
| Manual single-label | 1,049 | `{"mood": 1.0}` (hard label) |
| Manual multi-label | 1,634 | Equal split: `{"mood1": 0.5, "mood2": 0.5}` |
| Classifier inferred | ~65,779 | MLPClassifier probabilities, threshold ≥ 0.05 |

**Sample entries:**

```json
{
  "christmas": {"happy": 1.0},
  "serial killer": {"afraid": 1.0},
  "revenge": {"angry": 1.0},
  "love triangle": {"sad": 0.394, "angry": 0.219, "happy": 0.168, ...},
  "conspiracy": {"interested": 0.412, "afraid": 0.298, "angry": 0.142, ...}
}
```

---

## Classifier Evaluation Artifacts (Phase 1b) — Tracked

Produced by `keyword_mood_classifier.py` during the 7-classifier comparison.

### keyword_classifier_results.csv

14-row DataFrame: 7 classifiers x 2 scaling variants (scaled/unscaled).

| Classifier | Scaling | Train Acc | Train F1 | Val Acc | Val Prec | Val Rec | Val F1 |
|---|---|---|---|---|---|---|---|
| MLPClassifier | Scaled | 0.9976 | 0.9972 | 0.8857 | 0.8047 | 0.7244 | 0.7597 |
| SVC | Scaled | 0.9702 | 0.9642 | 0.8667 | 0.8062 | 0.6803 | 0.7156 |
| LogisticRegression | Scaled | 0.9274 | 0.9102 | 0.8571 | 0.7601 | 0.6778 | 0.7048 |
| KNN (k=5) | Scaled | 0.8869 | 0.8684 | 0.8190 | 0.7105 | 0.5990 | 0.6258 |
| GaussianNB | Scaled | 0.8214 | 0.8126 | 0.7524 | 0.6903 | 0.6434 | 0.6517 |
| Dummy (most_frequent) | Scaled | 0.3155 | 0.0758 | 0.2952 | 0.0422 | 0.1429 | 0.0651 |
| Dummy (stratified) | Scaled | 0.1667 | 0.1530 | 0.1619 | 0.1473 | 0.1448 | 0.1361 |

**Key findings:** MLPClassifier wins on Val F1. Train-Val gap of ~0.24 indicates moderate overfitting. All real classifiers massively outperform both DummyClassifier baselines.

### keyword_classifier_confusion_matrix.png

7x7 confusion matrix of the best classifier (MLPClassifier) on the held-out test set. Shows which moods are confused with each other. Main confusions: Angry↔Afraid, Surprised↔Interested.

---

## Runtime Loading

Loaded by `src/scoring/loader.py:_load_model_arrays()` as lazy singleton (~3 GB into RAM, first call only).

---

## Totals

| Category | Files | Size |
|---|---|---|
| Gitignored (SVD vectors + pkl models) | 6 | ~4.1 GB |
| Tracked (categorical arrays + mood + quality + JSON + eval) | 10 | ~224 MB |
| **Total** | **16** | **~4.3 GB** |
