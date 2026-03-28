"""SQLite persistence layer for the movie recommender.

Provides all database operations for the app: CRUD for user ratings, mood
reactions, watchlist, dismissed movies, streaming subscriptions, preferences,
profile cache, and movie details. Also provides aggregate query functions
for the Statistics dashboard.

Architecture:
    - Session state is the runtime source of truth (fast reads)
    - This module handles load-on-start (hydrate session state from SQLite)
      and save-on-change (persist every user action immediately)
    - Movie details stored with JSON columns (genres, cast_members,
      crew_members, countries, keywords) to avoid join tables while still
      supporting json_each() aggregation in Statistics queries

Database: data/user.sqlite (gitignored, WAL journal mode for concurrency).
Tables: watchlist, user_ratings, user_rating_moods, dismissed,
    user_subscriptions, user_preferences, user_profile_cache, movie_details.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Final

# Default streaming country code (avoids circular import from app.utils)
_DEFAULT_COUNTRY_CODE: Final[str] = "CH"

# Database path: project_root/data/ (three levels up: utils/ → app/ → root)
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = _DATA_DIR / "user.sqlite"


@contextmanager
def _connection():
    """Open a connection to the SQLite database.

    Creates the data/ directory and database file if they don't exist.
    Uses WAL journal mode for better concurrent read performance.

    Yields:
        sqlite3.Connection with Row factory for dict-like access.
    """
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
    """Create database tables if they don't exist.

    Core tables:
    - watchlist: saved movies with metadata for display
    - user_ratings: integer ratings (0-100 in steps of 10) per movie
    - user_rating_moods: mood reactions per rating (7 Ekman moods)
    - dismissed: movies the user skipped
    - user_subscriptions: streaming provider preferences
    - user_preferences: key-value store for user settings (country, language)
    - user_profile_cache: cached ML profile vectors (BLOB)
    - movie_details: TMDB metadata + JSON columns for genres, cast, crew,
      countries, keywords (Statistics dashboard + ML cache)

    Called once at app startup from streamlit_app.py.
    """
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
    """Load all watchlist entries from the database.

    Returns movie dicts compatible with TMDB API format (id, title,
    poster_path, vote_average, overview, genre_ids).

    Returns:
        List of movie dicts, newest first.
    """
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
    """Save a movie to the watchlist table.

    Uses INSERT OR REPLACE to handle re-adding the same movie.

    Args:
        movie: TMDB movie dict with at least "id" and "title" keys.
    """
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
    """Remove a movie from the watchlist.

    Args:
        movie_id: TMDB movie ID to remove.
    """
    with _connection() as conn:
        conn.execute("DELETE FROM watchlist WHERE movie_id = ?", (movie_id,))
        conn.commit()


# --- Ratings ---


def load_ratings() -> dict[int, int]:
    """Load all ratings from the database.

    Returns:
        Dict mapping movie_id (int) to rating (int, 0-100 in steps of 10).
    """
    with _connection() as conn:
        rows = conn.execute(
            "SELECT movie_id, rating FROM user_ratings"
        ).fetchall()
    return {row["movie_id"]: row["rating"] for row in rows}


def save_rating(movie_id: int, rating: int) -> None:
    """Save or update a movie rating.

    Args:
        movie_id: TMDB movie ID.
        rating: Integer rating from 0 to 100 (steps of 10).
    """
    with _connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO user_ratings (movie_id, rating)
               VALUES (?, ?)""",
            (movie_id, rating),
        )
        conn.commit()


# --- Mood Reactions ---


def save_mood_reactions(movie_id: int, moods: list[str]) -> None:
    """Save mood reactions for a rated movie.

    Replaces any existing mood reactions for the movie. Valid moods:
    Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry.

    Args:
        movie_id: TMDB movie ID (must exist in user_ratings).
        moods: List of mood strings (may be empty).
    """
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
    """Load all mood reactions from the database.

    Returns:
        Dict mapping movie_id to list of mood strings.
    """
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
    """Load all dismissed movie IDs from the database.

    Returns:
        Set of dismissed TMDB movie IDs.
    """
    with _connection() as conn:
        rows = conn.execute("SELECT movie_id FROM dismissed").fetchall()
    return {row["movie_id"] for row in rows}


def save_dismissed(movie_id: int) -> None:
    """Save a dismissed movie ID.

    Uses INSERT OR IGNORE to silently skip duplicates.

    Args:
        movie_id: TMDB movie ID that was dismissed.
    """
    with _connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO dismissed (movie_id) VALUES (?)",
            (movie_id,),
        )
        conn.commit()


# --- Subscriptions ---


def load_subscriptions() -> set[int]:
    """Load saved streaming provider IDs.

    Returns:
        Set of TMDB provider IDs the user subscribes to.
    """
    with _connection() as conn:
        rows = conn.execute("SELECT provider_id FROM user_subscriptions").fetchall()
    return {row["provider_id"] for row in rows}


def save_subscriptions(provider_ids: list[int], country: str = _DEFAULT_COUNTRY_CODE) -> None:
    """Replace all saved streaming subscriptions.

    Deletes existing entries and inserts the new selection. Uses a single
    transaction for atomicity.

    Args:
        provider_ids: List of TMDB provider IDs to save.
        country: ISO 3166-1 country code for the subscription region.
    """
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
    """Load a single user preference by key.

    Args:
        key: Preference key (e.g., "streaming_country", "preferred_language").
        default: Value to return if the key does not exist.

    Returns:
        Stored value as string, or default if not found.
    """
    with _connection() as conn:
        row = conn.execute(
            "SELECT value FROM user_preferences WHERE key = ?", (key,),
        ).fetchone()
    if row is None:
        return default
    return row["value"]


def save_preference(key: str, value: str) -> None:
    """Save a single user preference.

    Args:
        key: Preference key.
        value: Preference value (stored as TEXT).
    """
    with _connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO user_preferences (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()


def delete_preference(key: str) -> None:
    """Delete a single user preference.

    Args:
        key: Preference key to remove.
    """
    with _connection() as conn:
        conn.execute("DELETE FROM user_preferences WHERE key = ?", (key,))
        conn.commit()


# --- Profile Cache ---


def save_profile_cache(key: str, value: bytes) -> None:
    """Save a BLOB value to the user_profile_cache table.

    Args:
        key: Cache key (e.g., "user_profile").
        value: Serialized bytes to store.
    """
    with _connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO user_profile_cache (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()


def load_profile_cache(key: str) -> bytes | None:
    """Load a BLOB value from the user_profile_cache table.

    Args:
        key: Cache key to look up.

    Returns:
        Stored bytes, or None if the key does not exist.
    """
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
    """Save TMDB movie details with JSON-serialized related data.

    Stores core metadata as scalar columns and related data (genres, cast,
    crew, countries, keywords) as JSON TEXT columns. Single INSERT OR REPLACE
    for idempotent updates.

    Cast: top 20 by billing_order (name, order, profile_path).
    Crew: top 20 by popularity, deduplicated by person ID with merged jobs
        (name, job, popularity, profile_path).

    Args:
        movie_id: TMDB movie ID.
        details: Full TMDB movie details dict from get_movie_details().
        keywords: Optional keyword list from get_movie_keywords().
            If None, keywords column is set to empty JSON array.
    """
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
    """Find movie IDs that have ratings but no cached details.

    Used for backfilling: identifies ratings that were saved before the
    movie_details table existed, so their TMDB data can be fetched once.

    Returns:
        List of TMDB movie IDs needing detail fetch.
    """
    with _connection() as conn:
        rows = conn.execute(
            """SELECT r.movie_id FROM user_ratings r
               LEFT JOIN movie_details d ON r.movie_id = d.movie_id
               WHERE d.movie_id IS NULL"""
        ).fetchall()
    return [row["movie_id"] for row in rows]


# --- Statistics queries ---


def load_stats_summary() -> dict:
    """Load aggregated statistics for rated movies.

    Joins ratings with movie_details to compute watch time metrics.
    Movies without cached details are counted but excluded from runtime stats.

    Returns:
        Dict with keys: rated_count, total_runtime_min, avg_runtime_min,
        avg_rating, watchlisted_count, dismissed_count.
    """
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
    """Load directors with the most rated movies, avg rating, and photo.

    Args:
        limit: Maximum number of directors to return.

    Returns:
        List of dicts with keys: name, movies, avg_rating, profile_path.
    """
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
    """Load user ratings paired with TMDB ratings for comparison.

    Only includes movies where both a user rating and a TMDB vote_average
    exist in the database. User ratings are 0-100, TMDB ratings are 0-10.

    Returns:
        List of (tmdb_rating, user_rating, title) tuples.
    """
    with _connection() as conn:
        rows = conn.execute(
            """SELECT d.vote_average, r.rating, d.title
               FROM user_ratings r
               JOIN movie_details d ON r.movie_id = d.movie_id
               WHERE d.vote_average IS NOT NULL"""
        ).fetchall()
    return [(row["vote_average"], row["rating"], row["title"]) for row in rows]


def load_top_actors(limit: int = 5) -> list[dict]:
    """Load actors appearing most frequently in rated movies with avg rating and photo.

    Args:
        limit: Maximum number of actors to return.

    Returns:
        List of dicts with keys: name, movies, avg_rating, profile_path.
    """
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
    """Load genre breakdown with count and average user rating.

    Each movie can have multiple genres. Returns genre name, number of
    rated movies in that genre, and the user's average rating for that genre.

    Returns:
        List of (genre_name, count, avg_rating) tuples, sorted by count desc.
    """
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
    """Load all rated movies with details for the Statistics table.

    Joins ratings with movie_details to get title, runtime, TMDB rating,
    and poster path. Sorted by user rating descending.

    Returns:
        List of dicts with keys: movie_id, title, runtime, vote_average,
        rating (int 0-100), poster_path.
    """
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
    """Load mood reaction counts across all rated movies.

    Each rating can have multiple mood tags, so a single movie may
    contribute to multiple mood counts.

    Returns:
        List of (mood, count) tuples, sorted by count descending.
    """
    with _connection() as conn:
        rows = conn.execute(
            """SELECT mood, COUNT(*) AS count
               FROM user_rating_moods
               GROUP BY mood
               ORDER BY count DESC"""
        ).fetchall()
    return [(row["mood"], row["count"]) for row in rows]
