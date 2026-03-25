# MIGRATION.md

Migration plan for the movie recommender app. The existing ML pipeline
and UI are being replaced. This document defines the new architecture,
data flows, scoring system, and ML pipeline.

**Created:** 2026-03-25
**Updated:** 2026-03-26

---

## Architecture Overview

The system has two phases with strict separation:

### Offline Phase (Training)

Uses the 8.2 GB TMDB SQLite database (`data/tmdb.db`, 1.17M movies,
30 tables) to precompute feature vectors and mood scores. This database
is never queried at runtime.

### Runtime Phase (Production)

Uses three data sources:

1. **TMDB API** -- live calls for search, discovery, movie details,
   configuration (genres, languages, certifications, providers)
2. **Precomputed model files** (~3 GB `.npy` arrays) -- feature vectors
   and mood scores for all 1.17M movies, indexed by movie ID
3. **Local user database** (~1 KB) -- ratings, mood tags, streaming
   subscriptions, cached user profile vectors

---

## UI Flows

---

### Flow 1: Rate a Movie

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
ratings using the precomputed model files.

---

### Flow 2: Discover a Movie

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

## API Calls

---

### App Startup (cached, 24h TTL)

5 calls, executed once and cached:

```
GET /3/genre/movie/list?language=en
GET /3/configuration/languages
GET /3/certification/movie/list
GET /3/watch/providers/movie?watch_region=DE&language=en
GET /3/configuration/countries?language=en
```

The provider call is re-fetched when the user changes their streaming
country.

---

### Flow 1: Rate a Movie

```
GET /3/search/movie?query={text}&language=en-US&page=1
GET /3/movie/{id}?language=en-US
```

2 calls per rating action. No `append_to_response` needed here since
only basic display data is required.

---

### Flow 2: Discover a Movie

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

## Scoring System

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
SVD vector from movies rated 1-3) and the candidate's keyword vector.
Demotes movies that are thematically similar to disliked movies.

---

### Dynamic Weights by Rating Count

The scoring weights shift based on how many movies the user has rated.
With few ratings, quality dominates. With many ratings, personalization
dominates.

| Rated Films | Keyword | Mood | Director | Actor | Decade | Language | Runtime | Quality | Contra |
|---|---|---|---|---|---|---|---|---|---|
| 0 (cold start) | 0.00 | 0.35 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.60 | 0.00 |
| 1-9 | 0.10 | 0.25 | 0.05 | 0.03 | 0.02 | 0.01 | 0.01 | 0.50 | 0.03 |
| 10-49 | 0.20 | 0.22 | 0.12 | 0.08 | 0.04 | 0.02 | 0.02 | 0.20 | 0.10 |
| 50+ (full) | 0.25 | 0.20 | 0.15 | 0.10 | 0.05 | 0.03 | 0.02 | 0.10 | 0.10 |

---

## ML Pipeline

---

### Offline Pipeline (run once, then on DB updates)

---

#### Stage 1: Feature Extraction

Input: `data/tmdb.db` (8.2 GB, 1.17M movies)

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

#### Stage 2: Mood Score Prediction

For each movie: 7 mood probabilities (happy, interested, surprised,
sad, disgusted, afraid, angry).

**Signal 1: Genre -> Mood mapping (19 manual rules)**

```
Comedy    -> {happy: 0.8, surprised: 0.2}
Horror    -> {afraid: 0.8, disgusted: 0.3}
Drama     -> {sad: 0.5, interested: 0.4}
Thriller  -> {surprised: 0.5, afraid: 0.4, interested: 0.3}
Romance   -> {happy: 0.6, sad: 0.3}
War       -> {angry: 0.5, sad: 0.5}
Crime     -> {angry: 0.4, interested: 0.4}
Documentary -> {interested: 0.8}
...
```

**Signal 2: Keyword -> Mood mapping (top-500 keywords, manual)**

```
"revenge"    -> {angry: 0.8}
"murder"     -> {afraid: 0.5, disgusted: 0.3}
"love"       -> {happy: 0.7}
"tragedy"    -> {sad: 0.9}
"plot twist" -> {surprised: 0.9}
...
```

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

#### Stage 3: Quality Scores

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

#### Stage 4: Save Mappings

Output:

```
model/
  genre_mood_map.json        19 entries
  keyword_mood_map.json      top-500 entries
  movie_id_index.json        1.17M entries
  svd_models/
    keyword_svd.pkl
    director_svd.pkl
    actor_svd.pkl
```

Script: `pipeline/04_build_index.py`

---

### Online Pipeline (per request)

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
   - user_contra_vec   = avg(keyword_svd[rated where rating <= 3])

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
data/tmdb.db                    8.2 GB    Full TMDB database, 30 tables, 1.17M movies
```

---

### Runtime: Model Files (read-only)

```
model/
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
  keyword_mood_map.json         ~500 entries   manual keyword -> mood rules
  svd_models/
    keyword_svd.pkl                            for transforming new movies
    director_svd.pkl
    actor_svd.pkl
```

Total: ~3 GB

---

### Runtime: User Database (read-write, local)

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

```
movie-recommender/
  data/
    tmdb.db                          TMDB raw data (8.2 GB, offline only)
    tmdb-keyword-frequencies.tsv     keyword frequency export
  model/
    keyword_svd_vectors.npy
    director_svd_vectors.npy
    actor_svd_vectors.npy
    genre_vectors.npy
    decade_vectors.npy
    language_vectors.npy
    runtime_normalized.npy
    mood_scores.npy
    quality_scores.npy
    movie_id_index.json
    genre_mood_map.json
    keyword_mood_map.json
    svd_models/
      keyword_svd.pkl
      director_svd.pkl
      actor_svd.pkl
  pipeline/
    01_extract_features.py
    02_predict_moods.py
    03_quality_scores.py
    04_build_index.py
  app/
    streamlit_app.py                 entry point (router, init, navigation)
    app_pages/
      discover.py                    14 filters + personalized scoring
      rate.py                        search/browse → rate + mood reactions
      watchlist.py                   poster grid → detail dialog + actions
      statistics.py                  KPIs, charts, rankings, table
    utils/
      __init__.py
      db.py                          SQLite persistence (user ratings, watchlist, dismissed)
      tmdb.py                        TMDB API client (cached)
      scoring.py                     scoring formula + dynamic weights
      filters.py                     TMDB API parameter builder + local mood filter
      user_profile.py                user profile computation from ratings
    static/                          Poppins font files (18 TTFs + OFL license)
  docs/
    tmdb-schema.mmd                  ER diagram of TMDB database
```
