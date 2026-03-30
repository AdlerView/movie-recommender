"""SQLite persistence layer. Schema and architecture: see DATA.md."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from src.constants import DEFAULT_COUNTRY_CODE

# Database path: project_root/data/ (two levels up: src/ → root)
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = _DATA_DIR / "user.sqlite"


@contextmanager
def _connection():
    """Context manager: SQLite connection with WAL mode and Row factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # WAL mode allows reads while writing (relevant for multi-tab usage)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create all tables if they don't exist. Schema: see UTILS.md."""
    with _connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS watchlist (
                movie_id     INTEGER PRIMARY KEY,
                title        TEXT NOT NULL,
                poster_path  TEXT,
                vote_average REAL,
                overview     TEXT,
                genre_ids    TEXT,
                added_at     TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS user_ratings (
                movie_id INTEGER PRIMARY KEY,
                rating   INTEGER NOT NULL CHECK (rating BETWEEN 0 AND 100),
                rated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS user_rating_moods (
                movie_id INTEGER NOT NULL,
                mood     TEXT NOT NULL,
                PRIMARY KEY (movie_id, mood),
                FOREIGN KEY (movie_id) REFERENCES user_ratings(movie_id)
            );
            CREATE TABLE IF NOT EXISTS dismissed (
                movie_id     INTEGER PRIMARY KEY,
                dismissed_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS user_subscriptions (
                provider_id INTEGER PRIMARY KEY,
                iso_3166_1  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_preferences (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS user_profile_cache (
                key   TEXT PRIMARY KEY,
                value BLOB
            );
            CREATE TABLE IF NOT EXISTS movie_details (
                movie_id          INTEGER PRIMARY KEY,
                title             TEXT NOT NULL,
                runtime           INTEGER,
                release_date      TEXT,
                vote_average      REAL,
                original_language TEXT,
                poster_path       TEXT,
                backdrop_path     TEXT,
                overview          TEXT,
                genres            TEXT,   -- JSON: [{"id":18,"name":"Drama"},...]
                cast_members      TEXT,   -- JSON: [{"name":"...","order":0,"profile_path":"..."},...]
                crew_members      TEXT,   -- JSON: [{"name":"...","job":"...","popularity":0,"profile_path":"..."},...]
                countries         TEXT,   -- JSON: [{"code":"US","name":"United States"},...]
                keywords          TEXT,   -- JSON: [{"id":616,"name":"witch"},...]
                fetched_at        TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()


# --- Watchlist ---


def load_watchlist() -> list[dict]:
    """Load watchlist as TMDB-compatible dicts, newest first."""
    with _connection() as conn:
        rows = conn.execute(
            "SELECT * FROM watchlist ORDER BY added_at DESC"
        ).fetchall()
    # Convert sqlite3.Row objects to TMDB-compatible dicts for Streamlit display
    movies = []
    for row in rows:
        movie = {  # Reconstruct the same dict shape as TMDB API responses
            "id": row["movie_id"],
            "title": row["title"],
            "poster_path": row["poster_path"],
            "vote_average": row["vote_average"],
            "overview": row["overview"],
            "genre_ids": json.loads(row["genre_ids"]) if row["genre_ids"] else [],
        }
        movies.append(movie)
    return movies


def save_to_watchlist(movie: dict) -> None:
    with _connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO watchlist
               (movie_id, title, poster_path, vote_average, overview, genre_ids)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                movie["id"],
                movie["title"],
                movie.get("poster_path"),
                movie.get("vote_average"),
                movie.get("overview"),
                json.dumps(movie.get("genre_ids", [])),
            ),
        )
        conn.commit()


def remove_from_watchlist(movie_id: int) -> None:
    with _connection() as conn:
        conn.execute("DELETE FROM watchlist WHERE movie_id = ?", (movie_id,))
        conn.commit()


# --- Ratings ---


def load_ratings() -> dict[int, int]:
    """Load all ratings as {movie_id: rating} dict."""
    with _connection() as conn:
        rows = conn.execute(
            "SELECT movie_id, rating FROM user_ratings"
        ).fetchall()
    return {row["movie_id"]: row["rating"] for row in rows}


def save_rating(movie_id: int, rating: int) -> None:
    with _connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO user_ratings (movie_id, rating)
               VALUES (?, ?)""",
            (movie_id, rating),
        )
        conn.commit()


# --- Mood Reactions ---


def save_mood_reactions(movie_id: int, moods: list[str]) -> None:
    """Replace mood reactions for a movie (delete + re-insert)."""
    with _connection() as conn:
        # Clear existing moods for this movie
        conn.execute(
            "DELETE FROM user_rating_moods WHERE movie_id = ?", (movie_id,),
        )
        # Insert new moods
        for mood in moods:
            conn.execute(
                "INSERT INTO user_rating_moods (movie_id, mood) VALUES (?, ?)",
                (movie_id, mood),
            )
        conn.commit()


def load_mood_reactions() -> dict[int, list[str]]:
    """Load all mood reactions as {movie_id: [mood, ...]} dict."""
    with _connection() as conn:
        rows = conn.execute(
            "SELECT movie_id, mood FROM user_rating_moods ORDER BY movie_id"
        ).fetchall()
    result: dict[int, list[str]] = {}
    for row in rows:
        result.setdefault(row["movie_id"], []).append(row["mood"])
    return result


# --- Dismissed ---


def load_dismissed() -> set[int]:
    with _connection() as conn:
        rows = conn.execute("SELECT movie_id FROM dismissed").fetchall()
    return {row["movie_id"] for row in rows}


def save_dismissed(movie_id: int) -> None:
    with _connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO dismissed (movie_id) VALUES (?)",
            (movie_id,),
        )
        conn.commit()


# --- Subscriptions ---


def load_subscriptions() -> set[int]:
    with _connection() as conn:
        rows = conn.execute("SELECT provider_id FROM user_subscriptions").fetchall()
    return {row["provider_id"] for row in rows}


def save_subscriptions(provider_ids: list[int], country: str = DEFAULT_COUNTRY_CODE) -> None:
    """Replace all subscriptions atomically."""
    with _connection() as conn:
        conn.execute("DELETE FROM user_subscriptions")
        for pid in provider_ids:
            conn.execute(
                "INSERT INTO user_subscriptions (provider_id, iso_3166_1) VALUES (?, ?)",
                (pid, country),
            )
        conn.commit()


# --- Preferences (generic key-value store) ---


def load_preference(key: str, default: str | None = None) -> str | None:
    """Load a user preference by key, with optional default."""
    with _connection() as conn:
        row = conn.execute(
            "SELECT value FROM user_preferences WHERE key = ?", (key,),
        ).fetchone()
    if row is None:
        return default
    return row["value"]


def save_preference(key: str, value: str) -> None:
    with _connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO user_preferences (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()


def delete_preference(key: str) -> None:
    with _connection() as conn:
        conn.execute("DELETE FROM user_preferences WHERE key = ?", (key,))
        conn.commit()


# --- Profile Cache ---


def save_profile_cache(key: str, value: bytes) -> None:
    with _connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO user_profile_cache (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()


def load_profile_cache(key: str) -> bytes | None:
    with _connection() as conn:
        row = conn.execute(
            "SELECT value FROM user_profile_cache WHERE key = ?",
            (key,),
        ).fetchone()
    return row["value"] if row else None


# --- Movie Details (single table with JSON columns) ---


def save_movie_details(
    movie_id: int,
    details: dict,
    keywords: list[dict] | None = None,
) -> None:
    """Save TMDB details as JSON columns. Cast: top 20 by billing. Crew: top 20 by popularity, deduped."""
    # Genres: [{id, name}]
    genres_json = json.dumps(details.get("genres", []))

    # Cast: top 20 by billing_order, selected fields only
    raw_cast = details.get("credits", {}).get("cast", [])[:20]
    cast_json = json.dumps([
        {
            "name": c["name"],
            "order": c.get("order", 99),
            "profile_path": c.get("profile_path"),
        }
        for c in raw_cast
    ])

    # Crew: deduplicate by person ID, merge jobs, top 20 by popularity
    raw_crew = details.get("credits", {}).get("crew", [])
    crew_by_id: dict[int, dict] = {}
    for c in raw_crew:
        pid = c["id"]
        if pid in crew_by_id:
            # Append job if not already present
            if c.get("job") and c["job"] not in crew_by_id[pid]["jobs"]:
                crew_by_id[pid]["jobs"].append(c["job"])
        else:
            crew_by_id[pid] = {
                "name": c["name"],
                "jobs": [c["job"]] if c.get("job") else [],
                "popularity": c.get("popularity", 0),
                "profile_path": c.get("profile_path"),
            }
    crew_sorted = sorted(crew_by_id.values(), key=lambda x: x["popularity"], reverse=True)[:20]
    crew_json = json.dumps([
        {
            "name": c["name"],
            "job": ", ".join(c["jobs"]),
            "popularity": c["popularity"],
            "profile_path": c["profile_path"],
        }
        for c in crew_sorted
    ])

    # Countries: [{code, name}]
    countries_json = json.dumps([
        {"code": c["iso_3166_1"], "name": c["name"]}
        for c in details.get("production_countries", [])
    ])

    # Keywords: [{id, name}]
    keywords_json = json.dumps(keywords or [])

    with _connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO movie_details
               (movie_id, title, runtime, release_date, vote_average,
                original_language, poster_path, backdrop_path, overview,
                genres, cast_members, crew_members, countries, keywords)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                movie_id,
                details.get("title", ""),
                details.get("runtime"),
                details.get("release_date"),
                details.get("vote_average"),
                details.get("original_language"),
                details.get("poster_path"),
                details.get("backdrop_path"),
                details.get("overview"),
                genres_json,
                cast_json,
                crew_json,
                countries_json,
                keywords_json,
            ),
        )
        conn.commit()


def get_ratings_without_details() -> list[int]:
    """Find movie IDs with ratings but no cached details (for backfill)."""
    with _connection() as conn:
        rows = conn.execute(
            """SELECT r.movie_id FROM user_ratings r
               LEFT JOIN movie_details d ON r.movie_id = d.movie_id
               WHERE d.movie_id IS NULL"""
        ).fetchall()
    return [row["movie_id"] for row in rows]


# --- Statistics queries ---


def load_stats_summary() -> dict:
    """Aggregated stats: rated/watchlisted/dismissed counts, runtime, avg rating."""
    with _connection() as conn:
        # Rating + runtime aggregates (LEFT JOIN: count all ratings,
        # but only sum runtime where details exist)
        row = conn.execute(
            """SELECT
                   COUNT(*)                    AS rated_count,
                   COALESCE(SUM(d.runtime), 0) AS total_runtime_min,
                   COALESCE(AVG(d.runtime), 0) AS avg_runtime_min,
                   COALESCE(AVG(r.rating), 0)  AS avg_rating
               FROM user_ratings r
               LEFT JOIN movie_details d ON r.movie_id = d.movie_id"""
        ).fetchone()
        # Watchlist and dismissed counts (simple COUNT queries)
        wl_count = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        dm_count = conn.execute("SELECT COUNT(*) FROM dismissed").fetchone()[0]

    return {
        "rated_count": row["rated_count"],
        "total_runtime_min": row["total_runtime_min"],
        "avg_runtime_min": round(row["avg_runtime_min"]),
        "avg_rating": row["avg_rating"],
        "watchlisted_count": wl_count,
        "dismissed_count": dm_count,
    }


def load_top_directors(limit: int = 5) -> list[dict]:
    """Top directors by rated movie count, with avg rating and photo."""
    with _connection() as conn:
        rows = conn.execute(
            """SELECT je.value->>'name' AS person_name,
                      COUNT(*) AS count,
                      ROUND(AVG(r.rating)) AS avg_rating,
                      je.value->>'profile_path' AS profile_path
               FROM user_ratings r
               JOIN movie_details d ON r.movie_id = d.movie_id,
                    json_each(d.crew_members) je
               WHERE je.value->>'job' LIKE '%Director%'
               GROUP BY person_name
               ORDER BY count DESC, avg_rating DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [
        {
            "name": row["person_name"],
            "movies": row["count"],
            "avg_rating": row["avg_rating"],
            "profile_path": row["profile_path"],
        }
        for row in rows
    ]


def load_user_vs_tmdb() -> list[tuple[float, int, str]]:
    """User vs TMDB ratings for scatter plot."""
    with _connection() as conn:
        rows = conn.execute(
            """SELECT d.vote_average, r.rating, d.title
               FROM user_ratings r
               JOIN movie_details d ON r.movie_id = d.movie_id
               WHERE d.vote_average IS NOT NULL"""
        ).fetchall()
    return [(row["vote_average"], row["rating"], row["title"]) for row in rows]


def load_top_actors(limit: int = 5) -> list[dict]:
    """Top actors by rated movie count, with avg rating and photo."""
    with _connection() as conn:
        rows = conn.execute(
            """SELECT je.value->>'name' AS person_name,
                      COUNT(*) AS count,
                      ROUND(AVG(r.rating)) AS avg_rating,
                      je.value->>'profile_path' AS profile_path
               FROM user_ratings r
               JOIN movie_details d ON r.movie_id = d.movie_id,
                    json_each(d.cast_members) je
               GROUP BY person_name
               ORDER BY count DESC, avg_rating DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [
        {
            "name": row["person_name"],
            "movies": row["count"],
            "avg_rating": row["avg_rating"],
            "profile_path": row["profile_path"],
        }
        for row in rows
    ]


def load_genre_ratings() -> list[tuple[str, int, float]]:
    """Genre breakdown: name, movie count, avg user rating."""
    with _connection() as conn:
        rows = conn.execute(
            """SELECT je.value->>'name' AS genre_name,
                      COUNT(*) AS count,
                      ROUND(AVG(r.rating)) AS avg_rating
               FROM user_ratings r
               JOIN movie_details d ON r.movie_id = d.movie_id,
                    json_each(d.genres) je
               GROUP BY genre_name
               ORDER BY count DESC"""
        ).fetchall()
    return [(row["genre_name"], row["count"], row["avg_rating"]) for row in rows]


def load_rated_movies_table() -> list[dict]:
    """All rated movies with details for the ratings table."""
    with _connection() as conn:
        rows = conn.execute(
            """SELECT r.movie_id, d.title, d.runtime, d.vote_average,
                      r.rating, d.poster_path
               FROM user_ratings r
               LEFT JOIN movie_details d ON r.movie_id = d.movie_id
               ORDER BY r.rating DESC""",
        ).fetchall()
    return [dict(row) for row in rows]


def load_mood_distribution() -> list[tuple[str, int]]:
    """Mood reaction counts across all ratings."""
    with _connection() as conn:
        rows = conn.execute(
            """SELECT mood, COUNT(*) AS count
               FROM user_rating_moods
               GROUP BY mood
               ORDER BY count DESC"""
        ).fetchall()
    return [(row["mood"], row["count"]) for row in rows]
