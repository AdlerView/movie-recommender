# OUTPUT

Pipeline-generated feature arrays, trained models, and mappings. All 1,174,069-row arrays share the same row ordering: `SELECT id FROM movies ORDER BY id` from `data/input/tmdb.sqlite`. The bidirectional mapping `movie_id_index.json` translates TMDB movie IDs to row indices at runtime.

Loaded once as a lazy singleton by `ml/scoring/user_profile.py:_load_model_arrays()` (~3 GB into RAM), then shared across all Streamlit sessions.

---

## Pipeline Phases

| Phase | Scripts | Outputs | Runtime |
|---|---|---|---|
| 1a: Feature extraction | `ml/extraction/01_extract_features.py` | 7 `.npy` arrays + 3 `.pkl` SVD models | ~3 min |
| 1b: Keyword classifier | `ml/classification/keyword_mood_classifier.py` | `keyword_mood_map.json` + 2 eval artifacts | ~3 min |
| 2: Mood prediction | `ml/classification/02_predict_moods.py` | `mood_scores.npy` | ~4h 18min |
| 3: Quality scores | `ml/extraction/03_quality_scores.py` | `quality_scores.npy` | <1s |
| 4: Build index | `ml/extraction/04_build_index.py` | `movie_id_index.json` + verification | <1s |

Run order: `01` + `03` (parallel) → `keyword_mood_classifier` → `02` → `04`

---

## SVD Feature Vectors (Phase 1a)

High-dimensional sparse relational data (movie has keyword X, director Y) compressed into dense 200-dim vector spaces via TF-IDF/binary weighting + `TruncatedSVD`. Used by `scoring.py` for cosine similarity between user profile and candidates.

| File | Shape | Size | Encoding | DB Source | Explained Variance |
|---|---|---|---|---|---|
| `keyword_svd_vectors.npy` | 1,174,069 x 200 | 939 MB | TF-IDF → SVD | `movie_keywords` (70,779 unique) | 33.7% |
| `director_svd_vectors.npy` | 1,174,069 x 200 | 939 MB | Binary → SVD | `movie_crew` WHERE job='Director' (~170K) | 2.8% |
| `actor_svd_vectors.npy` | 1,174,069 x 200 | 939 MB | Binary → SVD | `movie_cast` WHERE cast_order<5 (~4M) | 1.7% |

Low director/actor explained variance reflects extreme sparsity (most people appear in 1-2 films), not poor component count.

**Gitignored** (too large for Git). Reproducible from `tmdb.sqlite` via `01_extract_features.py`.

---

## SVD Models (Phase 1a)

Fitted `TruncatedSVD` instances saved for potential future use (transforming new movies without refitting on the full corpus).

| File | Size | Transforms |
|---|---|---|
| `keyword_svd.pkl` | 57 MB | TF-IDF sparse matrix → 200-dim dense |
| `director_svd.pkl` | 345 MB | Binary sparse matrix → 200-dim dense |
| `actor_svd.pkl` | 909 MB | Binary sparse matrix → 200-dim dense |

**Gitignored.** Reproducible via `01_extract_features.py`.

---

## Categorical Feature Vectors (Phase 1a)

Low-dimensional one-hot/multi-hot vectors. No SVD needed. Used by `scoring.py` for cosine similarity.

| File | Shape | Size | Encoding | DB Source | Semantics |
|---|---|---|---|---|---|
| `genre_vectors.npy` | 1,174,069 x 19 | 89 MB | Multi-hot | `movie_genres` (19 TMDB genres) | 1.0 at each genre position; films can have multiple genres |
| `decade_vectors.npy` | 1,174,069 x 15 | 70 MB | Single-hot | `movies.release_date` | 13 decades (1900s-2020s) + pre-1900 + unknown |
| `language_vectors.npy` | 1,174,069 x 20 | 94 MB | Single-hot | `movies.original_language` | Top 19 languages by count + "other" |
| `runtime_normalized.npy` | 1,174,069 x 1 | 4.7 MB | Scalar [0,1] | `movies.runtime` | `min(runtime / 360, 1.0)`; NULL → 0.0 |

**Tracked** in Git (small enough, ~258 MB total).

---

## Mood Scores (Phase 2)

Per-movie mood probabilities from 4 combined signals: genre→mood mapping, keyword→mood mapping, emotion classifier on overviews (distilroberta), emotion classifier on reviews. Dynamic weighting based on signal availability (see `ml/classification/CLASSIFICATION.md`).

| File | Shape | Size | Columns | Coverage |
|---|---|---|---|---|
| `mood_scores.npy` | 1,174,069 x 7 | 33 MB | happy, interested, surprised, sad, disgusted, afraid, angry | 94.6% (1.11M/1.17M have scores > 0) |

Consumed by `mood_filter.py` (threshold filter on Discover page) and `scoring.py` (mood_match signal). **Tracked.**

---

## Quality Scores (Phase 3)

Bayesian average correcting for vote count bias: `quality = (v*R + m*C) / (v+m)` where m=median(vote_counts), C=mean(vote_averages). Normalized to [0,1].

| File | Shape | Size | Range |
|---|---|---|---|
| `quality_scores.npy` | 1,174,069 x 1 | 4.7 MB | [0.0, 1.0] |

At v>>m: score ≈ actual average. At v<<m: pulled toward global mean (~6.0). At v=0: score = global mean. Consumed by `scoring.py` (quality signal, weight 0.10-0.60 depending on rating count). **Tracked.**

---

## Index + Mappings (Phase 1b + 4)

| File | Entries | Size | Format | Purpose |
|---|---|---|---|---|
| `movie_id_index.json` | 1,174,069 | 19 MB | `{"tmdb_id": row_index}` | Bidirectional lookup: TMDB movie ID ↔ `.npy` row index. Required by all runtime scoring. |
| `keyword_mood_map.json` | 68,462 | 3.1 MB | `{"keyword_name": {"mood": weight}}` | Keyword → mood scores. 1,049 single-label (manual, weight=1.0) + 1,634 multi-label (manual, equal weight) + ~65K inferred (MLPClassifier probabilities, threshold ≥ 0.05). |

Both **tracked.** `movie_id_index.json` produced by `04_build_index.py`. `keyword_mood_map.json` produced by `keyword_mood_classifier.py`, consumed by `02_predict_moods.py` as Signal 2.

---

## Classifier Evaluation Artifacts (Phase 1b)

Produced by `keyword_mood_classifier.py` during the 7-classifier comparison. Displayed on the Statistics page and referenced in the ML evaluation notebook.

| File | Size | Content |
|---|---|---|
| `keyword_classifier_results.csv` | 1.9 KB | 14-row DataFrame: 7 classifiers x scaled/unscaled, columns: Classifier, Scaling, Train Acc, Train F1, Val Acc, Val Prec, Val Rec, Val F1 |
| `keyword_classifier_confusion_matrix.png` | 55 KB | 7x7 confusion matrix of best classifier (MLPClassifier) on held-out test set |

Both **tracked.**

---

## Runtime Loading

`user_profile.py:_load_model_arrays()` loads all 9 `.npy` arrays + `movie_id_index.json` into a `_ModelArrays` dataclass. Lazy singleton pattern — first call loads ~3 GB, subsequent calls return cached instance.

```python
_ModelArrays(
    movie_id_index,        # dict[str, int] — 1.17M entries
    keyword_svd,           # (1174069, 200) — cosine sim for keyword preferences
    director_svd,          # (1174069, 200) — cosine sim for director preferences
    actor_svd,             # (1174069, 200) — cosine sim for actor preferences
    genre_vectors,         # (1174069, 19)  — cosine sim for genre preferences
    decade_vectors,        # (1174069, 15)  — cosine sim for decade preferences
    language_vectors,      # (1174069, 20)  — cosine sim for language preferences
    runtime_normalized,    # (1174069, 1)   — |user_pref - candidate| distance
    mood_scores,           # (1174069, 7)   — mood filter + mood match signal
    quality_scores,        # (1174069, 1)   — Bayesian quality baseline signal
)
```

---

## Totals

| Category | Files | Size |
|---|---|---|
| Gitignored (SVD vectors + pkl models) | 6 | ~4.1 GB |
| Tracked (categorical arrays + mood + quality + JSON + eval) | 10 | ~224 MB |
| **Total** | **16** | **~4.3 GB** |
