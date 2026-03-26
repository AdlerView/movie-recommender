# UTILS

App utilities: SQLite persistence (`db.py`) and TMDB API client (`tmdb.py`).

---

## API Request Flow

### App Startup (cached, 24h TTL)

7 calls, executed once and cached:

```
GET /3/configuration                            24h
GET /3/genre/movie/list?language=en             24h
GET /3/configuration/languages                  24h
GET /3/certification/movie/list                 24h
GET /3/watch/providers/movie?watch_region=XX    24h + on country change
GET /3/watch/providers/regions?language=en       24h
GET /3/configuration/countries?language=en       24h
```

### Flow 1: Rate a Movie (3 calls)

```
GET /3/search/movie?query={text}&language=en-US&page=1   5m
GET /3/movie/{id}?language=en-US                         1h
GET /3/movie/{id}/keywords                               24h
```

Keywords fetched on save for caching in the local database.

### Flow 2: Discover a Movie (~25 calls)

```
GET /3/search/keyword?query={text}&page=1                5m   (autocomplete)
GET /3/discover/movie?with_genres=...&page=1              10m  (1-5 pages)
GET /3/movie/{id}?append_to_response=watch/providers,...  1h   (top-20 parallel)
```

Total per discovery request: ~25 API calls, ~500ms with parallel execution.

---

## User Database Schema

Runtime SQLite (`data/user.sqlite`), schema v5 via `PRAGMA user_version`:

```sql
CREATE TABLE user_ratings (
    movie_id   INTEGER PRIMARY KEY,
    rating     INTEGER NOT NULL CHECK (rating BETWEEN 0 AND 100),
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

Additional normalized tables for Statistics: `movie_details`, `movie_genres`,
`movie_cast`, `movie_crew`, `movie_countries`, `movie_keywords`. See `db.py`
`init_db()` for the full schema.
