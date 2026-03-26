# INPUT

Pipeline source data. These files are consumed by the offline ML pipeline scripts.

---

## File Inventory

| File | Size | Tracked | Consumed by |
|---|---|---|---|
| `tmdb.sqlite` | 7.7 GB | Gitignored | `01_extract_features.py`, `02_predict_moods.py`, `03_quality_scores.py` |
| `tmdb-keyword-frequencies_labeled_top5000.tsv` | 355 KB | Tracked | `keyword_mood_classifier.py` |
| `genre_mood_map.json` | 1.3 KB | Tracked | `02_predict_moods.py` |

---

## tmdb.sqlite

Offline TMDB database (1,174,069 movies, 30 tables). Built by a one-time fetch script (not in this repo). Never queried at runtime — only used by the offline pipeline to produce `.npy` arrays in `data/output/`.

Key tables used by the pipeline:

| Table | Used by | Purpose |
|---|---|---|
| `movies` | Stage 1, 3 | release_date, runtime, original_language, vote_average, vote_count, overview, tagline |
| `movie_keywords` + `keywords` | Stage 1 | Keyword TF-IDF → SVD vectors |
| `movie_genres` + `genres` | Stage 1 | Genre one-hot vectors |
| `movie_crew` | Stage 1 | Director one-hot → SVD (WHERE job='Director') |
| `movie_cast` | Stage 1 | Actor one-hot → SVD (WHERE cast_order < 5) |
| `movie_reviews` | Stage 2 | Review text for emotion classification |

---

## tmdb-keyword-frequencies_labeled_top5000.tsv

Top 5,000 TMDB keywords by movie_count, manually labeled with mood assignments. Training data for the keyword-to-mood classifier.

**Columns:** `keyword_id`, `keyword_name`, `movie_count`, `assigned_moods`, `assignment_type`, `confidence`, `short_reason`

**Rows:** 5,000 (+ header)

| assignment_type | Count |
|---|---|
| single | 1,049 |
| multi | 1,634 |
| none | 2,317 |

Only the single-label subset (1,049) is used for classifier training. See `ml/classification/CLASSIFICATION.md` for full distribution and labeling rules.

---

## genre_mood_map.json

Hand-crafted mapping of 19 TMDB genres to mood weights. 19 entries, each mapping a genre name to a dict of mood scores (independent weights, not normalized to 1.0).

```json
{"Action": {"interested": 0.5, "afraid": 0.3}, ...}
```

Used by `02_predict_moods.py` as Signal 1 (genre → mood). See `ml/classification/CLASSIFICATION.md` for the full mapping table.
