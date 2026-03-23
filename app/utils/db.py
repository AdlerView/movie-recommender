"""SQLite persistence layer for the movie recommender.

Stores watchlist entries, ratings, and dismissals in a local SQLite database.
Session state is the runtime source of truth; this module handles load-on-start
and save-on-change persistence. Uses Python's sqlite3 stdlib module.

Database file: data/movies.db (gitignored).
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

    Three tables:
    - watchlist: saved movies with metadata for display
    - ratings: decimal ratings (0.00-10.00) per movie, matching TMDB scale
    - dismissed: movies the user skipped

    Includes schema migration from v1 (INTEGER 1-5) to v2 (REAL 0.00-10.00).
    Called once at app startup from streamlit_app.py.
    """
    with _connection() as conn:
        # --- Schema migration ---
        # v0/v1: ratings used INTEGER 1-5 (star rating)
        # v2: ratings use REAL 0.00-10.00 (TMDB-compatible decimal scale)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 2:
            # Drop old ratings table (incompatible schema)
            conn.execute("DROP TABLE IF EXISTS ratings")
            conn.execute("PRAGMA user_version = 2")

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
            CREATE TABLE IF NOT EXISTS ratings (
                movie_id INTEGER PRIMARY KEY,
                rating   REAL NOT NULL CHECK (rating >= 0.0 AND rating <= 10.0),
                rated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS dismissed (
                movie_id     INTEGER PRIMARY KEY,
                dismissed_at TEXT DEFAULT (datetime('now'))
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
    # Convert rows to TMDB-compatible dicts
    movies = []
    for row in rows:
        movie = {
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
