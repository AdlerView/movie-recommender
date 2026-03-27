# INPUT

Pipeline source data. These files are consumed by the offline ML pipeline scripts to produce the `.npy` feature arrays in `data/output/`. The largest file (`tmdb.sqlite`, 7.7 GB) is gitignored — this document serves as the authoritative reference for its schema and contents.

---

## File Inventory

| File | Size | Tracked | Consumed by |
|---|---|---|---|
| `tmdb.sqlite` | 7.7 GB | Gitignored | `extract_features.py`, `predict_moods.py`, `quality_scores.py` |
| `labeled_keywords.tsv` | 355 KB | Tracked | `keyword_mood_classifier.py` |
| `genre_mood_map.json` | 1.3 KB | Tracked | `predict_moods.py` |

---

## tmdb.sqlite — Offline TMDB Database

**1,174,069 movies, 30 tables, 7.7 GB.** Built by a one-time bulk fetch script (not in this repo). Never queried at runtime — only used by the offline pipeline to produce `.npy` arrays. The full database is too large for Git but is reproducible from the TMDB API.

---

### Core Table: `movies`

The central table. One row per movie. All pipeline stages read from this table.

```sql
CREATE TABLE movies (
    id                INTEGER PRIMARY KEY,  -- TMDB movie ID (e.g., 550 = Fight Club)
    title             TEXT,                 -- English title
    original_title    TEXT,                 -- Title in original language
    original_language TEXT,                 -- ISO 639-1 code (e.g., "en", "ko", "ja")
    release_date      TEXT,                 -- "YYYY-MM-DD" or partial (e.g., "2024")
    runtime           INTEGER,             -- Minutes (NULL for ~40% of movies)
    vote_average      REAL,                -- 0.0-10.0 (TMDB user rating)
    vote_count        INTEGER,             -- Number of votes (0 to 35,000+)
    popularity        REAL,                -- TMDB popularity score (0 to 500+)
    overview          TEXT,                -- English plot summary (NULL for ~15%)
    tagline           TEXT,                -- Marketing tagline (NULL for ~70%)
    budget            INTEGER,
    revenue           INTEGER,
    status            TEXT,                -- "Released", "Post Production", etc.
    adult             INTEGER              -- 0 or 1
);
```

**Row count:** 1,174,069

**Sample rows:**

| id | title | original_language | release_date | runtime | vote_average | vote_count |
|---|---|---|---|---|---|---|
| 550 | Fight Club | en | 1999-10-15 | 139 | 8.434 | 29,462 |
| 680 | Pulp Fiction | en | 1994-09-10 | 154 | 8.487 | 27,853 |
| 155 | The Dark Knight | en | 2008-07-16 | 152 | 8.516 | 33,479 |
| 496243 | Parasite | ko | 2019-05-30 | 133 | 8.511 | 18,384 |
| 19404 | Dilwale Dulhania Le Jayenge | hi | 1995-10-20 | 190 | 8.7 | 4,399 |

**Statistics:**
- Movies with runtime: ~700K (60%), NULL: ~474K (40%)
- Movies with overview: ~996K (85%), NULL: ~178K (15%)
- Movies with ≥1 vote: ~580K (49%), zero votes: ~594K (51%)
- Top languages: en (456K), ja (68K), fr (51K), ko (41K), es (37K)

---

### Relational Tables (used by Stage 1)

#### `movie_keywords` + `keywords`

Many-to-many: movies ↔ thematic keyword tags.

```sql
CREATE TABLE keywords (
    id   INTEGER PRIMARY KEY,  -- Keyword ID
    name TEXT                  -- e.g., "time travel", "dystopia", "based on novel"
);
CREATE TABLE movie_keywords (
    movie_id   INTEGER REFERENCES movies(id),
    keyword_id INTEGER REFERENCES keywords(id),
    PRIMARY KEY (movie_id, keyword_id)
);
```

- **Unique keywords:** 70,779
- **Total movie-keyword pairs:** 4,121,437
- **Average keywords per movie:** 3.5 (movies with ≥1 keyword: ~830K)
- **Top keywords by movie count:** "woman director" (62K), "independent film" (37K), "based on novel" (15K)

Used by: `extract_features.py` → TF-IDF sparse matrix → TruncatedSVD → `keyword_svd_vectors.npy` (1.17M × 200)

#### `movie_genres` + `genres`

Many-to-many: movies ↔ TMDB genres.

```sql
CREATE TABLE genres (
    id   INTEGER PRIMARY KEY,  -- e.g., 28 = Action, 18 = Drama
    name TEXT                  -- 19 total genres
);
CREATE TABLE movie_genres (
    movie_id INTEGER REFERENCES movies(id),
    genre_id INTEGER REFERENCES genres(id),
    PRIMARY KEY (movie_id, genre_id)
);
```

- **Genres:** 19 (Action, Adventure, Animation, Comedy, Crime, Documentary, Drama, Family, Fantasy, History, Horror, Music, Mystery, Romance, Science Fiction, TV Movie, Thriller, War, Western)
- **Total movie-genre pairs:** 2,156,789
- **Average genres per movie:** 1.8
- **Most common:** Drama (412K), Comedy (213K), Thriller (143K)

Used by: `extract_features.py` → multi-hot matrix → `genre_vectors.npy` (1.17M × 19)

#### `movie_crew`

One row per crew member per movie.

```sql
CREATE TABLE movie_crew (
    movie_id  INTEGER REFERENCES movies(id),
    person_id INTEGER,
    job       TEXT,       -- "Director", "Producer", "Screenplay", etc.
    name      TEXT,
    popularity REAL
);
```

- **Total rows:** ~8.5M
- **Unique directors:** ~170K (filtered via `WHERE job = 'Director'`)
- **Director-movie pairs:** ~1.2M

Used by: `extract_features.py` → binary sparse matrix (Director only) → SVD → `director_svd_vectors.npy` (1.17M × 200)

#### `movie_cast`

One row per cast member per movie, ordered by billing.

```sql
CREATE TABLE movie_cast (
    movie_id   INTEGER REFERENCES movies(id),
    person_id  INTEGER,
    name       TEXT,
    character  TEXT,       -- Role name (e.g., "The Narrator")
    cast_order INTEGER,    -- 0 = top-billed, 1 = second, etc.
    popularity REAL
);
```

- **Total rows:** ~15M
- **Unique actors:** ~4M
- **Filtered pairs (cast_order < 5):** ~4.2M (top 5 billed per film)

Used by: `extract_features.py` → binary sparse matrix (top-5 cast only) → SVD → `actor_svd_vectors.npy` (1.17M × 200)

#### `movie_reviews`

User reviews from TMDB (English text, variable length).

```sql
CREATE TABLE movie_reviews (
    id       TEXT PRIMARY KEY,  -- TMDB review ID
    movie_id INTEGER REFERENCES movies(id),
    author   TEXT,
    content  TEXT,              -- Full review text (up to several thousand words)
    rating   REAL               -- Author's rating (often NULL)
);
```

- **Total reviews:** ~95K across ~38,535 movies (3.3% of all movies)
- **Average reviews per movie (where exists):** 2.5

Used by: `predict_moods.py` → emotion classifier (distilroberta) → Signal 4 (review emotion)

---

## labeled_keywords.tsv — Training Data for Mood Classifier

Top 5,000 TMDB keywords by movie_count, each manually labeled with one or more of 7 Ekman moods. This is the training data for the keyword-to-mood classifier (`keyword_mood_classifier.py`).

**Columns:**

| Column | Type | Description | Example |
|---|---|---|---|
| `keyword_id` | int | TMDB keyword ID | 818 |
| `keyword_name` | str | Keyword text | "based on novel" |
| `movie_count` | int | Movies using this keyword | 15,234 |
| `assigned_moods` | str | Comma-separated moods | "Interested" or "Sad,Afraid" |
| `assignment_type` | str | single / multi / none | "single" |
| `confidence` | str | high / medium / low | "high" |
| `short_reason` | str | Labeling rationale | "Knowledge, discovery" |

**Distribution:**

| assignment_type | Count | Usage |
|---|---|---|
| single | 1,049 | Classifier training (7-class classification) |
| multi | 1,634 | Direct mapping to `keyword_mood_map.json` (equal weights) |
| none | 2,317 | Excluded (no emotional connotation) |

**Sample rows:**

```tsv
keyword_id  keyword_name       movie_count  assigned_moods       assignment_type  confidence
9663        love               38756        Happy,Sad            multi            high
10349       revenge            7431         Angry                single           high
9748        murder             12891        Afraid,Angry         multi            high
14819       detective          3285         Interested           single           high
```

Only the **single-label subset (1,049)** is used for classifier training. See `ml/classification/CLASSIFICATION.md` for the full labeling rules, correction statistics, and class distribution analysis.

---

## genre_mood_map.json — Hand-Crafted Genre-to-Mood Rules

Maps each of the 19 TMDB genres to mood weights. Weights are independent (not normalized to 1.0) and reflect the emotional connotation of the genre itself.

**Full mapping:**

```json
{
  "Action":          {"interested": 0.5, "afraid": 0.3},
  "Adventure":       {"happy": 0.4, "interested": 0.4, "surprised": 0.3},
  "Animation":       {"happy": 0.5, "sad": 0.2, "interested": 0.2},
  "Comedy":          {"happy": 0.8, "surprised": 0.2},
  "Crime":           {"angry": 0.4, "interested": 0.4, "afraid": 0.2},
  "Documentary":     {"interested": 0.6, "sad": 0.2, "angry": 0.1},
  "Drama":           {"sad": 0.5, "interested": 0.4},
  "Family":          {"happy": 0.5, "sad": 0.2},
  "Fantasy":         {"interested": 0.5, "surprised": 0.3, "happy": 0.2},
  "History":         {"interested": 0.6, "sad": 0.3, "angry": 0.1},
  "Horror":          {"afraid": 0.7, "disgusted": 0.3},
  "Music":           {"happy": 0.6, "interested": 0.3, "sad": 0.1},
  "Mystery":         {"interested": 0.5, "surprised": 0.4, "afraid": 0.2},
  "Romance":         {"happy": 0.6, "sad": 0.3},
  "Science Fiction":  {"interested": 0.5, "surprised": 0.3, "afraid": 0.2},
  "TV Movie":        {},
  "Thriller":        {"afraid": 0.5, "interested": 0.4, "surprised": 0.2},
  "War":             {"angry": 0.5, "sad": 0.5, "afraid": 0.2},
  "Western":         {"interested": 0.4, "happy": 0.2, "angry": 0.2}
}
```

Used by `predict_moods.py` as **Signal 1** (genre → mood). For multi-genre movies, mood scores are averaged across genres. See `ml/classification/CLASSIFICATION.md` for the rationale behind each mapping.
