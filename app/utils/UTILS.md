# UTILS

App utilities: SQLite persistence (`db.py`) and TMDB API client (`tmdb.py`).

Used endpoints and caching strategy documented below. Full TMDB API reference: [developer.themoviedb.org](https://developer.themoviedb.org/reference/)

---

## TMDB API (tmdb.py)

---

### Authentication

API key via query parameter, injected lazily inside `_get()` on each request
(not at module import — avoids crash when `secrets.toml` is missing).
Rate limit: ~40 req/s, respect HTTP 429.

---

### Image URLs

```
https://image.tmdb.org/t/p/{size}/{file_path}
```

Hardcoded `IMAGE_BASE` in tmdb.py. `poster_url()` helper builds full URL.

| Size | Use case |
|------|----------|
| `w342` | Card posters (default) |
| `w500` | Detail view |

---

### append_to_response

`get_movie_details()` uses `append_to_response=credits,videos,watch/providers,release_dates,reviews`
to combine 6 requests into 1. Max 20 appended requests per call.

---

### Pagination

20 items/page, max 500 pages. Response includes `total_pages`, `total_results`.

---

### Endpoints Used by tmdb.py

**Configuration (cached 24h via `@st.cache_data`):**

| Function | Endpoint | Returns |
|---|---|---|
| `get_genres()` | `GET /genre/movie/list` | `[{id, name}]` — 19 genres |
| `get_languages()` | `GET /configuration/languages` | `[{iso_639_1, english_name, name}]` |
| `get_certifications(country)` | `GET /certification/movie/list` | `[{certification, meaning, order}]` per country |
| `get_countries()` | `GET /configuration/countries` | `[{iso_3166_1, english_name}]` |
| `get_watch_providers_list(region)` | `GET /watch/providers/movie?watch_region=XX` | `[{provider_id, provider_name, logo_path}]` |

**Discovery + Search (cached 5-10m):**

| Function | Endpoint | Key params | Returns |
|---|---|---|---|
| `discover_movies_filtered(params, page)` | `GET /discover/movie` | `with_genres`, `certification_country`, `certification.lte`, `primary_release_date.gte/lte`, `with_original_language`, `with_runtime.gte/lte`, `vote_average.gte/lte`, `vote_count.gte`, `with_keywords`, `watch_region`, `with_watch_providers`, `with_watch_monetization_types`, `sort_by`, `page` | `{results, total_results, total_pages}` |
| `search_movies(query, page)` | `GET /search/movie` | `query`, `page` | `[{id, title, poster_path, vote_average, overview, genre_ids, release_date}]` |
| `search_keywords(query)` | `GET /search/keyword` | `query` | `[{id, name}]` |

**Per-movie details (cached 1h):**

| Function | Endpoint | Returns |
|---|---|---|
| `get_movie_details(movie_id)` | `GET /movie/{id}?append_to_response=credits,videos,watch/providers,release_dates,reviews` | Full details + credits + videos + watch/providers + release_dates + reviews |
| `get_movie_keywords(movie_id)` | `GET /movie/{id}/keywords` | `[{id, name}]` — thematic tags |

**Discover parameter logic:** Comma = AND, pipe = OR. `with_genres=53,18` (both), `with_keywords=10349|285685` (any). `certification.lte` uses the `order` field from certification list, not numeric value.

---

### Error Codes

| HTTP | Code | Meaning |
|------|------|---------|
| 401 | 7 | Invalid API key |
| 404 | 34 | Resource not found |
| 422 | 22 | Invalid page (must be 1-500) |
| 429 | 25 | Rate limit exceeded |

---

### Attribution

> "This product uses the TMDB API but is not endorsed or certified by TMDB."

---

## API Request Flows

---

### App Startup (cached 24h)

```
GET /genre/movie/list?language=en
GET /configuration/languages
GET /certification/movie/list
GET /configuration/countries?language=en
GET /watch/providers/movie?watch_region=XX
```

Provider list re-fetched when user changes streaming country in Settings.

---

### Flow 1: Rate a Movie (3 calls)

```
GET /search/movie?query={text}&language=en-US&page=1   5m
GET /movie/{id}?append_to_response=credits,videos,watch/providers,release_dates,reviews   1h
GET /movie/{id}/keywords                               24h
```

Keywords fetched on save for caching in SQLite (keyword badges + ML pipeline).

---

### Flow 2: Discover a Movie (~25 calls)

```
GET /search/keyword?query={text}&page=1                5m   (autocomplete)
GET /discover/movie?with_genres=...&page=1              10m  (1-5 pages)
GET /movie/{id}?append_to_response=...                  1h   (top-20 parallel)
```

Total: ~25 API calls, ~500ms with parallel execution.

### Combined Discover Call Example

```
GET /discover/movie
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

Already-rated movies excluded locally (no TMDB API parameter for this).

---

## Caching Strategy

### Configuration (app startup)

| Call | TTL |
|---|---|
| `genre/movie/list` | 24h |
| `configuration/languages` | 24h |
| `certification/movie/list` | 24h |
| `configuration/countries` | 24h |
| `watch/providers/movie?watch_region=XX` | 24h + on country change |

### Per-request

| Call | TTL | Rationale |
|---|---|---|
| `discover/movie?...` | 10m | Bounded key space |
| `search/movie?query=...` | 5m | Unbounded key space |
| `search/keyword?query=...` | 5m | Unbounded key space |

### Per-movie

| Call | TTL | Rationale |
|---|---|---|
| `movie/{id}` (details) | 1h | Votes change slowly |
| `movie/{id}/keywords` | 24h | Keywords rarely change |
| `movie/{id}/watch/providers` | 1h | Licensing changes weekly |

---

## User Database Schema (db.py)

Runtime SQLite (`data/user.sqlite`), WAL mode, all tables via `CREATE TABLE IF NOT EXISTS`.

**Core tables:**

```sql
user_ratings (movie_id PK, rating INTEGER 0-100, rated_at TEXT)
user_rating_moods (movie_id, mood TEXT, PK(movie_id, mood))
watchlist (movie_id PK, title, poster_path, vote_average, overview, genre_ids, added_at)
dismissed (movie_id PK, dismissed_at)
user_subscriptions (provider_id PK, iso_3166_1)
user_preferences (key PK, value TEXT)
user_profile_cache (key PK, value BLOB) — accessed via save_profile_cache() / load_profile_cache()
```

**Movie details (single table with JSON columns):**

```sql
movie_details (
    movie_id PK, title, runtime, release_date, vote_average,
    original_language, poster_path, backdrop_path, overview,
    genres TEXT,        -- JSON: [{"id":18,"name":"Drama"},...]
    cast_members TEXT,  -- JSON: [{"name":"...","order":0,"profile_path":"..."},...]  (top 20)
    crew_members TEXT,  -- JSON: [{"name":"...","job":"...","popularity":0,"profile_path":"..."},...] (top 20, deduped)
    countries TEXT,     -- JSON: [{"code":"US","name":"United States"},...]
    keywords TEXT,      -- JSON: [{"id":616,"name":"witch"},...]
    fetched_at TEXT
)
```

`save_movie_details(movie_id, details, keywords=)` saves everything in one INSERT OR REPLACE. Statistics queries use `json_each()` for genre/cast/crew aggregation. `get_ratings_without_details()` finds ratings needing backfill.
