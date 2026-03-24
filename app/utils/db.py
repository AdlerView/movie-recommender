"""SQLite persistence layer for the movie recommender.

Stores watchlist entries, ratings, dismissals, and cached TMDB movie details
in a local SQLite database. Session state is the runtime source of truth;
this module handles load-on-start and save-on-change persistence.

Schema is fully normalized: movie_details holds core metadata, with separate
junction tables for genres, cast, crew, and production countries. This
enables efficient SQL aggregations for the Statistics dashboard without
re-fetching from TMDB.

Database file: data/movies.db (gitignored).
Schema version: 4 (managed via PRAGMA user_version).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Database path: project_root/data/movies.db (two levels up from utils/)
DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "movies.db"


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

    Core tables (v2):
    - watchlist: saved movies with metadata for display
    - ratings: decimal ratings (0.00-10.00) per movie, matching TMDB scale
    - dismissed: movies the user skipped

    Normalized detail tables (v3+, for Statistics dashboard):
    - movie_details: core TMDB metadata (runtime, release_date, etc.)
    - movie_genres: genre assignments per movie (many-to-many)
    - movie_cast: top 5 cast members per movie by billing order
    - movie_crew: directors per movie (filtered on job='Director')
    - movie_countries: production countries per movie
    - movie_keywords: thematic tags per movie (v4, for ML + keyword cloud)

    Called once at app startup from streamlit_app.py.
    """
    with _connection() as conn:
        # --- Schema migration ---
        version = conn.execute("PRAGMA user_version").fetchone()[0]

        # v0/v1 → v2: ratings changed from INTEGER 1-5 to REAL 0.00-10.00
        if version < 2:
            conn.execute("DROP TABLE IF EXISTS ratings")

        conn.executescript("""
            -- Watchlist: saved movies with TMDB metadata for offline display
            CREATE TABLE IF NOT EXISTS watchlist (
                movie_id     INTEGER PRIMARY KEY,
                title        TEXT NOT NULL,
                poster_path  TEXT,
                vote_average REAL,
                overview     TEXT,
                genre_ids    TEXT,    -- JSON array of TMDB genre IDs
                added_at     TEXT DEFAULT (datetime('now'))
            );
            -- Ratings: decimal 0.00-10.00 matching the TMDB scale
            CREATE TABLE IF NOT EXISTS ratings (
                movie_id INTEGER PRIMARY KEY,
                rating   REAL NOT NULL CHECK (rating >= 0.0 AND rating <= 10.0),
                rated_at TEXT DEFAULT (datetime('now'))
            );
            -- Dismissed: movies skipped via "Not interested" button
            CREATE TABLE IF NOT EXISTS dismissed (
                movie_id     INTEGER PRIMARY KEY,
                dismissed_at TEXT DEFAULT (datetime('now'))
            );
            -- v3: Normalized TMDB detail tables for Statistics dashboard
            -- Core movie metadata cached from GET /movie/{id}
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
                fetched_at        TEXT DEFAULT (datetime('now'))
            );
            -- Genre assignments (many-to-many, from details.genres)
            CREATE TABLE IF NOT EXISTS movie_genres (
                movie_id   INTEGER NOT NULL,
                genre_id   INTEGER NOT NULL,
                genre_name TEXT NOT NULL,
                PRIMARY KEY (movie_id, genre_id),
                FOREIGN KEY (movie_id) REFERENCES movie_details(movie_id)
            );
            -- Top cast members (from details.credits.cast, order < 5)
            CREATE TABLE IF NOT EXISTS movie_cast (
                movie_id      INTEGER NOT NULL,
                person_id     INTEGER NOT NULL,
                person_name   TEXT NOT NULL,
                character     TEXT,
                billing_order INTEGER NOT NULL,
                PRIMARY KEY (movie_id, person_id),
                FOREIGN KEY (movie_id) REFERENCES movie_details(movie_id)
            );
            -- Crew members filtered to directors (from details.credits.crew)
            CREATE TABLE IF NOT EXISTS movie_crew (
                movie_id    INTEGER NOT NULL,
                person_id   INTEGER NOT NULL,
                person_name TEXT NOT NULL,
                job         TEXT NOT NULL,
                PRIMARY KEY (movie_id, person_id, job),
                FOREIGN KEY (movie_id) REFERENCES movie_details(movie_id)
            );
            -- Production countries (from details.production_countries)
            CREATE TABLE IF NOT EXISTS movie_countries (
                movie_id     INTEGER NOT NULL,
                country_code TEXT NOT NULL,
                country_name TEXT NOT NULL,
                PRIMARY KEY (movie_id, country_code),
                FOREIGN KEY (movie_id) REFERENCES movie_details(movie_id)
            );
            -- v4: Thematic keywords per movie (from /movie/{id}/keywords)
            CREATE TABLE IF NOT EXISTS movie_keywords (
                movie_id     INTEGER NOT NULL,
                keyword_id   INTEGER NOT NULL,
                keyword_name TEXT NOT NULL,
                PRIMARY KEY (movie_id, keyword_id),
                FOREIGN KEY (movie_id) REFERENCES movie_details(movie_id)
            );
        """)

        # Bump schema version to current
        if version < 4:
            conn.execute("PRAGMA user_version = 4")

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


def load_ratings() -> dict[int, float]:
    """Load all ratings from the database.

    Returns:
        Dict mapping movie_id (int) to rating (float, 0.00-10.00).
    """
    with _connection() as conn:
        rows = conn.execute("SELECT movie_id, rating FROM ratings").fetchall()
    return {row["movie_id"]: row["rating"] for row in rows}


def save_rating(movie_id: int, rating: float) -> None:
    """Save or update a movie rating.

    Args:
        movie_id: TMDB movie ID.
        rating: Decimal rating from 0.00 to 10.00.
    """
    with _connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO ratings (movie_id, rating)
               VALUES (?, ?)""",
            (movie_id, rating),
        )
        conn.commit()


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


# --- Movie Details (normalized cache for Statistics) ---


def save_movie_details(movie_id: int, details: dict) -> None:
    """Save TMDB movie details to normalized tables.

    Parses the full TMDB response (with appended credits) and distributes
    data across movie_details, movie_genres, movie_cast, movie_crew, and
    movie_countries tables. Uses DELETE + INSERT for idempotent updates.

    Args:
        movie_id: TMDB movie ID.
        details: Full TMDB movie details dict from get_movie_details().
    """
    with _connection() as conn:
        # Core metadata
        conn.execute(
            """INSERT OR REPLACE INTO movie_details
               (movie_id, title, runtime, release_date, vote_average,
                original_language, poster_path, backdrop_path, overview)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            ),
        )

        # Genres — clear and re-insert for idempotent updates
        conn.execute("DELETE FROM movie_genres WHERE movie_id = ?", (movie_id,))
        for genre in details.get("genres", []):
            conn.execute(
                """INSERT INTO movie_genres (movie_id, genre_id, genre_name)
                   VALUES (?, ?, ?)""",
                (movie_id, genre["id"], genre["name"]),
            )

        # Cast — top 5 by billing order (main cast only)
        conn.execute("DELETE FROM movie_cast WHERE movie_id = ?", (movie_id,))
        for member in details.get("credits", {}).get("cast", [])[:5]:
            conn.execute(
                """INSERT INTO movie_cast
                   (movie_id, person_id, person_name, character, billing_order)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    movie_id,
                    member["id"],
                    member["name"],
                    member.get("character"),
                    member.get("order", 99),
                ),
            )

        # Crew — directors only (job == "Director")
        conn.execute("DELETE FROM movie_crew WHERE movie_id = ?", (movie_id,))
        for member in details.get("credits", {}).get("crew", []):
            if member.get("job") == "Director":
                conn.execute(
                    """INSERT INTO movie_crew
                       (movie_id, person_id, person_name, job)
                       VALUES (?, ?, ?, ?)""",
                    (movie_id, member["id"], member["name"], "Director"),
                )

        # Production countries
        conn.execute(
            "DELETE FROM movie_countries WHERE movie_id = ?", (movie_id,),
        )
        for country in details.get("production_countries", []):
            conn.execute(
                """INSERT INTO movie_countries
                   (movie_id, country_code, country_name)
                   VALUES (?, ?, ?)""",
                (movie_id, country["iso_3166_1"], country["name"]),
            )

        conn.commit()


def save_movie_keywords(movie_id: int, keywords: list[dict]) -> None:
    """Save TMDB keywords for a movie.

    Fetched separately from movie details via get_movie_keywords().
    Uses DELETE + INSERT for idempotent updates.

    Args:
        movie_id: TMDB movie ID.
        keywords: List of keyword dicts with "id" and "name" keys.
    """
    with _connection() as conn:
        conn.execute(
            "DELETE FROM movie_keywords WHERE movie_id = ?", (movie_id,),
        )
        for kw in keywords:
            conn.execute(
                """INSERT INTO movie_keywords (movie_id, keyword_id, keyword_name)
                   VALUES (?, ?, ?)""",
                (movie_id, kw["id"], kw["name"]),
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
            """SELECT r.movie_id FROM ratings r
               LEFT JOIN movie_details d ON r.movie_id = d.movie_id
               WHERE d.movie_id IS NULL"""
        ).fetchall()
    return [row["movie_id"] for row in rows]


def get_ratings_without_keywords() -> list[int]:
    """Find rated movie IDs that have no cached keywords.

    Used for backfilling keywords separately from movie details,
    since keywords are fetched via a dedicated API endpoint.

    Returns:
        List of TMDB movie IDs needing keyword fetch.
    """
    with _connection() as conn:
        rows = conn.execute(
            """SELECT r.movie_id FROM ratings r
               LEFT JOIN movie_keywords k ON r.movie_id = k.movie_id
               WHERE k.movie_id IS NULL"""
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
               FROM ratings r
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


def load_genre_distribution() -> list[tuple[str, int]]:
    """Load genre counts across all rated movies.

    Each movie can have multiple genres, so a single movie may contribute
    to multiple genre counts. Only includes genres from rated movies.

    Returns:
        List of (genre_name, count) tuples, sorted by count descending.
    """
    with _connection() as conn:
        rows = conn.execute(
            """SELECT g.genre_name, COUNT(*) AS count
               FROM ratings r
               JOIN movie_genres g ON r.movie_id = g.movie_id
               GROUP BY g.genre_name
               ORDER BY count DESC"""
        ).fetchall()
    return [(row["genre_name"], row["count"]) for row in rows]


def load_top_directors(limit: int = 5) -> list[tuple[str, int]]:
    """Load directors with the most rated movies.

    Args:
        limit: Maximum number of directors to return.

    Returns:
        List of (director_name, movie_count) tuples, sorted by count desc.
    """
    with _connection() as conn:
        rows = conn.execute(
            """SELECT c.person_name, COUNT(*) AS count
               FROM ratings r
               JOIN movie_crew c ON r.movie_id = c.movie_id
               WHERE c.job = 'Director'
               GROUP BY c.person_id
               ORDER BY count DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [(row["person_name"], row["count"]) for row in rows]


def load_user_vs_tmdb() -> list[tuple[float, float, str]]:
    """Load user ratings paired with TMDB ratings for comparison.

    Only includes movies where both a user rating and a TMDB vote_average
    exist in the database.

    Returns:
        List of (tmdb_rating, user_rating, title) tuples.
    """
    with _connection() as conn:
        rows = conn.execute(
            """SELECT d.vote_average, r.rating, d.title
               FROM ratings r
               JOIN movie_details d ON r.movie_id = d.movie_id
               WHERE d.vote_average IS NOT NULL"""
        ).fetchall()
    return [(row["vote_average"], row["rating"], row["title"]) for row in rows]


def load_rating_distribution() -> list[float]:
    """Load all user ratings for histogram visualization.

    Returns:
        List of rating values (0.00-10.00).
    """
    with _connection() as conn:
        rows = conn.execute("SELECT rating FROM ratings").fetchall()
    return [row["rating"] for row in rows]


def load_rating_history() -> list[tuple[str, float]]:
    """Load user ratings in chronological order.

    Returns each rating with its timestamp for a line chart showing
    how the user's ratings evolve over time.

    Returns:
        List of (rated_at, rating) tuples, sorted by time ascending.
    """
    with _connection() as conn:
        rows = conn.execute(
            """SELECT r.rated_at, r.rating
               FROM ratings r
               WHERE r.rated_at IS NOT NULL
               ORDER BY r.rated_at ASC"""
        ).fetchall()
    return [(row["rated_at"], row["rating"]) for row in rows]


def load_language_distribution() -> list[tuple[str, int]]:
    """Load movie counts grouped by original language.

    Uses the original_language field from movie_details (ISO 639-1 codes).
    Movies without a language are excluded.

    Returns:
        List of (language_code, count) tuples, sorted by count descending.
    """
    with _connection() as conn:
        rows = conn.execute(
            """SELECT d.original_language AS lang, COUNT(*) AS count
               FROM ratings r
               JOIN movie_details d ON r.movie_id = d.movie_id
               WHERE d.original_language IS NOT NULL
               GROUP BY d.original_language
               ORDER BY count DESC"""
        ).fetchall()
    return [(row["lang"].upper(), row["count"]) for row in rows]


def load_decade_distribution() -> list[tuple[str, int]]:
    """Load movie counts grouped by release decade.

    Groups rated movies into decades (2020s, 2010s, etc.) based on
    the release_date field. Movies without a release date are excluded.

    Returns:
        List of (decade_label, count) tuples, sorted by decade descending.
    """
    with _connection() as conn:
        rows = conn.execute(
            """SELECT (CAST(substr(d.release_date, 1, 4) AS INTEGER) / 10) * 10
                      AS decade,
                      COUNT(*) AS count
               FROM ratings r
               JOIN movie_details d ON r.movie_id = d.movie_id
               WHERE d.release_date IS NOT NULL AND length(d.release_date) >= 4
               GROUP BY decade
               ORDER BY decade DESC"""
        ).fetchall()
    return [(f"{row['decade']}s", row["count"]) for row in rows]


def load_top_actors(limit: int = 5) -> list[tuple[str, int]]:
    """Load actors appearing most frequently in rated movies.

    Only counts top-5-billed cast members (billing_order < 5) to focus
    on lead actors rather than minor roles.

    Args:
        limit: Maximum number of actors to return.

    Returns:
        List of (actor_name, movie_count) tuples, sorted by count desc.
    """
    with _connection() as conn:
        rows = conn.execute(
            """SELECT c.person_name, COUNT(*) AS count
               FROM ratings r
               JOIN movie_cast c ON r.movie_id = c.movie_id
               GROUP BY c.person_id
               ORDER BY count DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [(row["person_name"], row["count"]) for row in rows]


def load_rated_movies_table() -> list[dict]:
    """Load all rated movies with details for the Statistics table.

    Joins ratings with movie_details to get title, runtime, TMDB rating,
    and poster path. Sorted by user rating descending.

    Returns:
        List of dicts with keys: movie_id, title, runtime, vote_average,
        rating, poster_path.
    """
    with _connection() as conn:
        rows = conn.execute(
            """SELECT r.movie_id, d.title, d.runtime, d.vote_average,
                      r.rating, d.poster_path
               FROM ratings r
               LEFT JOIN movie_details d ON r.movie_id = d.movie_id
               ORDER BY r.rating DESC""",
        ).fetchall()
    return [dict(row) for row in rows]
