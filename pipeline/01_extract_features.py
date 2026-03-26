#!/usr/bin/env python3
"""Feature extraction pipeline (Stage 1).

Transforms the TMDB SQLite database into compact numerical feature vectors
for runtime scoring. Each movie gets one vector per feature dimension.
Sparse relational data (movie has keyword X, director Y) is converted into
dense vector spaces via TF-IDF weighting and SVD dimensionality reduction.

Course foundation:
    - TfidfTransformer: same math as TfidfVectorizer in Notebook 10-2
      (Brexit tweets), applied to structured keyword IDs instead of raw text
    - Feature scaling and selection: Notebooks 10-0, 11

Beyond-course extensions:
    - TruncatedSVD for dimensionality reduction (motivated by Curse of
      Dimensionality, lecture 11 slides 8-10: 70K features → 200 features)
    - Binary sparse matrices for director/actor co-occurrence
    - One-hot encoding for categorical features (genres, decades, languages)

Data flow:
    store/tmdb.db (1.17M movies, 30 tables)
        → 7 .npy feature arrays in store/
        → 3 .pkl SVD models in store/svd_models/

All arrays share the same row ordering: SELECT id FROM movies ORDER BY id.
The movie_id ↔ row_index mapping is saved by Stage 4 (04_build_index.py).
"""
from __future__ import annotations

import argparse
import logging
import pickle
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def load_movie_ids(conn: sqlite3.Connection) -> np.ndarray:
    """Load canonical movie ID ordering.

    All feature arrays use this ordering: row i corresponds to movie_ids[i].
    Deterministic via ORDER BY id.

    Args:
        conn: SQLite connection to tmdb.db.

    Returns:
        1D numpy array of movie IDs, sorted ascending.
    """
    df = pd.read_sql_query("SELECT id FROM movies ORDER BY id", conn)
    movie_ids = df["id"].to_numpy()
    log.info("Loaded %d movie IDs (min=%d, max=%d)", len(movie_ids), movie_ids.min(), movie_ids.max())
    return movie_ids


def build_id_mapping(ids: np.ndarray) -> dict[int, int]:
    """Build a mapping from ID to row index.

    Args:
        ids: Sorted array of IDs.

    Returns:
        Dict mapping each ID to its position in the array.
    """
    return {int(mid): i for i, mid in enumerate(ids)}


def extract_keyword_svd(
    conn: sqlite3.Connection,
    movie_row: dict[int, int],
    n_movies: int,
    n_components: int,
    output_dir: Path,
) -> None:
    """Extract keyword features via TF-IDF and SVD.

    Uses TfidfTransformer on a binary movie-keyword sparse matrix, then
    reduces to n_components dimensions with TruncatedSVD. Same approach
    as TfidfVectorizer in course Notebook 10-2, but on structured keyword
    IDs instead of raw text tokens.

    Args:
        conn: SQLite connection to tmdb.db.
        movie_row: Mapping from movie_id to row index.
        n_movies: Total number of movies.
        n_components: Number of SVD dimensions.
        output_dir: Directory for .npy and .pkl output.
    """
    log.info("--- Keyword TF-IDF → SVD (%d components) ---", n_components)

    # Load movie-keyword pairs
    df = pd.read_sql_query("SELECT movie_id, keyword_id FROM movie_keywords", conn)
    log.info("Loaded %d movie-keyword pairs", len(df))

    # Map keyword IDs to contiguous column indices
    unique_keywords = df["keyword_id"].unique()
    kw_to_col = {int(kid): i for i, kid in enumerate(unique_keywords)}
    n_keywords = len(unique_keywords)
    log.info("Unique keywords: %d", n_keywords)

    # Build sparse matrix (movies × keywords, binary)
    rows = [movie_row[mid] for mid in df["movie_id"] if mid in movie_row]
    cols = [kw_to_col[kid] for mid, kid in zip(df["movie_id"], df["keyword_id"]) if mid in movie_row]
    data = np.ones(len(rows), dtype=np.float32)
    sparse = csr_matrix((data, (rows, cols)), shape=(n_movies, n_keywords))
    log.info("Sparse matrix: %s, nnz=%d", sparse.shape, sparse.nnz)

    # TF-IDF weighting (same math as TfidfVectorizer in Notebook 10-2)
    tfidf = TfidfTransformer()
    sparse_tfidf = tfidf.fit_transform(sparse)
    log.info("TF-IDF applied")

    # SVD dimensionality reduction (beyond course: Curse of Dimensionality fix)
    svd = TruncatedSVD(n_components=n_components, random_state=42)
    vectors = svd.fit_transform(sparse_tfidf).astype(np.float32)
    explained = svd.explained_variance_ratio_.sum()
    log.info("SVD: %s, explained variance: %.2f%%", vectors.shape, explained * 100)

    # Save outputs
    np.save(output_dir / "keyword_svd_vectors.npy", vectors)
    with open(output_dir / "svd_models" / "keyword_svd.pkl", "wb") as f:
        pickle.dump(svd, f)
    log.info("Saved keyword_svd_vectors.npy + keyword_svd.pkl")


def extract_person_svd(
    conn: sqlite3.Connection,
    movie_row: dict[int, int],
    n_movies: int,
    n_components: int,
    output_dir: Path,
    query: str,
    name: str,
    npy_filename: str,
    pkl_filename: str,
) -> None:
    """Extract person (director/actor) features via binary sparse matrix and SVD.

    No TF-IDF here — directors/actors are binary (movie has person or not).
    IDF would over-weight rare persons, which is less meaningful for people
    than for keywords.

    Args:
        conn: SQLite connection to tmdb.db.
        movie_row: Mapping from movie_id to row index.
        n_movies: Total number of movies.
        n_components: Number of SVD dimensions.
        output_dir: Directory for .npy and .pkl output.
        query: SQL query returning (movie_id, person_id) pairs.
        name: Display name for logging (e.g., "Director", "Actor").
        npy_filename: Output filename for vectors (e.g., "director_svd_vectors.npy").
        pkl_filename: Output filename for SVD model (e.g., "director_svd.pkl").
    """
    log.info("--- %s binary → SVD (%d components) ---", name, n_components)

    df = pd.read_sql_query(query, conn)
    log.info("Loaded %d %s pairs", len(df), name.lower())

    # Map person IDs to contiguous column indices
    unique_persons = df["person_id"].unique()
    person_to_col = {int(pid): i for i, pid in enumerate(unique_persons)}
    n_persons = len(unique_persons)
    log.info("Unique %ss: %d", name.lower(), n_persons)

    # Build binary sparse matrix
    rows = []
    cols = []
    for mid, pid in zip(df["movie_id"], df["person_id"]):
        if mid in movie_row:
            rows.append(movie_row[mid])
            cols.append(person_to_col[int(pid)])
    data = np.ones(len(rows), dtype=np.float32)
    sparse = csr_matrix((data, (rows, cols)), shape=(n_movies, n_persons))
    log.info("Sparse matrix: %s, nnz=%d", sparse.shape, sparse.nnz)

    # SVD (no TF-IDF — binary presence is the signal)
    svd = TruncatedSVD(n_components=n_components, random_state=42)
    vectors = svd.fit_transform(sparse).astype(np.float32)
    explained = svd.explained_variance_ratio_.sum()
    log.info("SVD: %s, explained variance: %.2f%%", vectors.shape, explained * 100)

    # Save outputs
    np.save(output_dir / npy_filename, vectors)
    with open(output_dir / "svd_models" / pkl_filename, "wb") as f:
        pickle.dump(svd, f)
    log.info("Saved %s + %s", npy_filename, pkl_filename)


def extract_genre_vectors(
    conn: sqlite3.Connection,
    movie_row: dict[int, int],
    n_movies: int,
    output_dir: Path,
) -> None:
    """Extract genre multi-hot vectors.

    Each film gets a 19-dim vector with 1.0 at the positions of its genres.
    Multi-hot because films can have multiple genres (e.g., Action + Thriller).
    No SVD needed — only 19 dimensions.

    Args:
        conn: SQLite connection to tmdb.db.
        movie_row: Mapping from movie_id to row index.
        n_movies: Total number of movies.
        output_dir: Directory for .npy output.
    """
    log.info("--- Genre multi-hot ---")

    # Load genre list (canonical column ordering)
    genres = pd.read_sql_query("SELECT id FROM genres ORDER BY id", conn)
    genre_ids = genres["id"].tolist()
    genre_to_col = {gid: i for i, gid in enumerate(genre_ids)}
    n_genres = len(genre_ids)
    log.info("Genre columns: %d", n_genres)

    # Load movie-genre pairs
    df = pd.read_sql_query("SELECT movie_id, genre_id FROM movie_genres", conn)
    log.info("Loaded %d movie-genre pairs", len(df))

    # Build multi-hot matrix
    vectors = np.zeros((n_movies, n_genres), dtype=np.float32)
    for mid, gid in zip(df["movie_id"], df["genre_id"]):
        if mid in movie_row and gid in genre_to_col:
            vectors[movie_row[mid], genre_to_col[gid]] = 1.0

    nonzero_rows = np.count_nonzero(vectors.sum(axis=1))
    log.info("Genre vectors: %s, films with genres: %d", vectors.shape, nonzero_rows)

    np.save(output_dir / "genre_vectors.npy", vectors)
    log.info("Saved genre_vectors.npy")


def extract_decade_vectors(
    conn: sqlite3.Connection,
    movie_row: dict[int, int],
    n_movies: int,
    output_dir: Path,
) -> None:
    """Extract decade single-hot vectors.

    15 bins: 1900s, 1910s, ..., 2020s, pre-1900, unknown.
    Each film belongs to exactly one decade.

    Args:
        conn: SQLite connection to tmdb.db.
        movie_row: Mapping from movie_id to row index.
        n_movies: Total number of movies.
        output_dir: Directory for .npy output.
    """
    log.info("--- Decade single-hot ---")

    # Decade bins: 1900-2020 (13 decades) + pre-1900 + unknown = 15
    decade_labels = [f"{d}s" for d in range(1900, 2030, 10)] + ["pre-1900", "unknown"]
    decade_to_col = {label: i for i, label in enumerate(decade_labels)}
    n_decades = len(decade_labels)

    df = pd.read_sql_query("SELECT id, release_date FROM movies ORDER BY id", conn)
    log.info("Loaded %d movies for decade extraction", len(df))

    vectors = np.zeros((n_movies, n_decades), dtype=np.float32)
    for _, row in df.iterrows():
        mid = row["id"]
        if mid not in movie_row:
            continue
        rid = movie_row[mid]
        rd = row["release_date"]
        if pd.isna(rd) or not isinstance(rd, str) or len(rd) < 4:
            vectors[rid, decade_to_col["unknown"]] = 1.0
            continue
        try:
            year = int(rd[:4])
        except ValueError:
            vectors[rid, decade_to_col["unknown"]] = 1.0
            continue
        if year < 1900:
            vectors[rid, decade_to_col["pre-1900"]] = 1.0
        else:
            decade = (year // 10) * 10
            label = f"{decade}s"
            if label in decade_to_col:
                vectors[rid, decade_to_col[label]] = 1.0
            else:
                vectors[rid, decade_to_col["unknown"]] = 1.0

    known = n_movies - int(vectors[:, decade_to_col["unknown"]].sum())
    log.info("Decade vectors: %s, known: %d, unknown: %d", vectors.shape, known, n_movies - known)

    np.save(output_dir / "decade_vectors.npy", vectors)
    log.info("Saved decade_vectors.npy")


def extract_language_vectors(
    conn: sqlite3.Connection,
    movie_row: dict[int, int],
    n_movies: int,
    top_n: int,
    output_dir: Path,
) -> None:
    """Extract language single-hot vectors for top-N languages.

    Top-N languages by movie count, plus an "other" bin for rare languages.
    Each film belongs to exactly one language.

    Args:
        conn: SQLite connection to tmdb.db.
        movie_row: Mapping from movie_id to row index.
        n_movies: Total number of movies.
        top_n: Number of top languages to include (rest → "other").
        output_dir: Directory for .npy output.
    """
    log.info("--- Language top-%d single-hot ---", top_n)

    # Determine top-N languages by frequency
    lang_counts = pd.read_sql_query(
        "SELECT original_language, COUNT(*) as c FROM movies "
        "WHERE original_language IS NOT NULL "
        "GROUP BY original_language ORDER BY c DESC",
        conn,
    )
    # Top N-1 languages + "other" bin = N columns
    top_langs = lang_counts["original_language"].head(top_n - 1).tolist()
    lang_to_col = {lang: i for i, lang in enumerate(top_langs)}
    other_col = top_n - 1  # last column
    log.info("Top %d languages: %s + other", top_n - 1, top_langs[:5])

    df = pd.read_sql_query("SELECT id, original_language FROM movies ORDER BY id", conn)

    vectors = np.zeros((n_movies, top_n), dtype=np.float32)
    for _, row in df.iterrows():
        mid = row["id"]
        if mid not in movie_row:
            continue
        rid = movie_row[mid]
        lang = row["original_language"]
        if lang in lang_to_col:
            vectors[rid, lang_to_col[lang]] = 1.0
        else:
            vectors[rid, other_col] = 1.0

    log.info("Language vectors: %s", vectors.shape)

    np.save(output_dir / "language_vectors.npy", vectors)
    log.info("Saved language_vectors.npy")


def extract_runtime(
    conn: sqlite3.Connection,
    movie_row: dict[int, int],
    n_movies: int,
    output_dir: Path,
) -> None:
    """Extract normalized runtime feature.

    Normalizes runtime by dividing by 360 minutes (practical maximum).
    NULL → 0.0 (neutral for cosine similarity).

    Args:
        conn: SQLite connection to tmdb.db.
        movie_row: Mapping from movie_id to row index.
        n_movies: Total number of movies.
        output_dir: Directory for .npy output.
    """
    log.info("--- Runtime normalized ---")

    df = pd.read_sql_query("SELECT id, runtime FROM movies ORDER BY id", conn)

    vectors = np.zeros((n_movies, 1), dtype=np.float32)
    for _, row in df.iterrows():
        mid = row["id"]
        if mid not in movie_row:
            continue
        rt = row["runtime"]
        if pd.notna(rt) and rt > 0:
            # Clamp to [0, 1] range (360 min = 6 hours as practical max)
            vectors[movie_row[mid], 0] = min(float(rt) / 360.0, 1.0)

    has_runtime = int((vectors > 0).sum())
    log.info("Runtime vectors: %s, with runtime: %d, without: %d", vectors.shape, has_runtime, n_movies - has_runtime)

    np.save(output_dir / "runtime_normalized.npy", vectors)
    log.info("Saved runtime_normalized.npy")


def main() -> int:
    """Run the feature extraction pipeline.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Extract feature vectors from TMDB database for scoring pipeline.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("store/tmdb.db"),
        help="Path to TMDB SQLite database (default: store/tmdb.db)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("store"),
        help="Output directory for .npy and .pkl files (default: store/)",
    )
    parser.add_argument(
        "--svd-components",
        type=int,
        default=200,
        help="Number of SVD dimensions (default: 200)",
    )
    parser.add_argument(
        "--top-languages",
        type=int,
        default=20,
        help="Number of top languages for onehot (default: 20)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        log.error("Database not found: %s", args.db)
        return 1

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "svd_models").mkdir(exist_ok=True)

    conn = sqlite3.connect(args.db)

    # --- Canonical movie ID ordering (shared by all features) ---
    log.info("=== Loading canonical movie ID ordering ===")
    movie_ids = load_movie_ids(conn)
    movie_row = build_id_mapping(movie_ids)
    n_movies = len(movie_ids)

    # --- Feature 1: Keywords (TF-IDF → SVD) ---
    log.info("=== Feature 1/7: Keywords ===")
    extract_keyword_svd(conn, movie_row, n_movies, args.svd_components, args.output)

    # --- Feature 2: Directors (binary → SVD) ---
    log.info("=== Feature 2/7: Directors ===")
    extract_person_svd(
        conn, movie_row, n_movies, args.svd_components, args.output,
        query="SELECT movie_id, person_id FROM movie_crew WHERE job = 'Director'",
        name="Director",
        npy_filename="director_svd_vectors.npy",
        pkl_filename="director_svd.pkl",
    )

    # --- Feature 3: Actors (binary → SVD, top-5 cast only) ---
    log.info("=== Feature 3/7: Actors ===")
    extract_person_svd(
        conn, movie_row, n_movies, args.svd_components, args.output,
        query="SELECT movie_id, person_id FROM movie_cast WHERE cast_order < 5",
        name="Actor",
        npy_filename="actor_svd_vectors.npy",
        pkl_filename="actor_svd.pkl",
    )

    # --- Feature 4: Genres (multi-hot) ---
    log.info("=== Feature 4/7: Genres ===")
    extract_genre_vectors(conn, movie_row, n_movies, args.output)

    # --- Feature 5: Decades (single-hot) ---
    log.info("=== Feature 5/7: Decades ===")
    extract_decade_vectors(conn, movie_row, n_movies, args.output)

    # --- Feature 6: Languages (top-N single-hot) ---
    log.info("=== Feature 6/7: Languages ===")
    extract_language_vectors(conn, movie_row, n_movies, args.top_languages, args.output)

    # --- Feature 7: Runtime (normalized) ---
    log.info("=== Feature 7/7: Runtime ===")
    extract_runtime(conn, movie_row, n_movies, args.output)

    conn.close()

    # --- Summary ---
    log.info("=== Summary ===")
    expected_files = [
        "keyword_svd_vectors.npy", "director_svd_vectors.npy", "actor_svd_vectors.npy",
        "genre_vectors.npy", "decade_vectors.npy", "language_vectors.npy",
        "runtime_normalized.npy",
    ]
    for fname in expected_files:
        fpath = args.output / fname
        if fpath.exists():
            arr = np.load(fpath)
            size_mb = fpath.stat().st_size / (1024 * 1024)
            log.info("  %-30s %s  %.1f MB", fname, arr.shape, size_mb)
        else:
            log.warning("  %-30s MISSING", fname)

    pkl_files = ["keyword_svd.pkl", "director_svd.pkl", "actor_svd.pkl"]
    for fname in pkl_files:
        fpath = args.output / "svd_models" / fname
        status = "OK" if fpath.exists() else "MISSING"
        log.info("  svd_models/%-20s %s", fname, status)

    return 0


if __name__ == "__main__":
    sys.exit(main())
