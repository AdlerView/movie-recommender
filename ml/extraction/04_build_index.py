#!/usr/bin/env python3
"""Build index pipeline (Stage 4).

Generates the movie_id ↔ row_index mapping used at runtime to look up
precomputed feature vectors by TMDB movie ID. Verifies that all pipeline
output files exist and have consistent row counts.

Data flow:
    data/input/tmdb.sqlite (SELECT id FROM movies ORDER BY id)
        → data/output/movie_id_index.json (bidirectional mapping)

Row ordering: same as Stage 1-3 (canonical ORDER BY id).
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Expected .npy files from pipeline Stages 1-3
EXPECTED_NPY = [
    "keyword_svd_vectors.npy",
    "director_svd_vectors.npy",
    "actor_svd_vectors.npy",
    "genre_vectors.npy",
    "decade_vectors.npy",
    "language_vectors.npy",
    "runtime_normalized.npy",
    "mood_scores.npy",
    "quality_scores.npy",
]


def main() -> int:
    """Build movie ID index and verify pipeline outputs.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Build movie_id_index.json and verify pipeline outputs.",
    )
    parser.add_argument(
        "--db", type=Path, default=Path("data/input/tmdb.sqlite"),
        help="Path to TMDB SQLite database (default: data/input/tmdb.sqlite)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/output"),
        help="Output directory (default: data/output/)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        log.error("Database not found: %s", args.db)
        return 1

    # --- Build movie_id_index.json ---
    log.info("=== Building movie ID index ===")
    conn = sqlite3.connect(args.db)
    cursor = conn.execute("SELECT id FROM movies ORDER BY id")
    movie_ids = [row[0] for row in cursor]
    conn.close()

    # Bidirectional mapping: movie_id (str) → row_index (int)
    index = {str(mid): i for i, mid in enumerate(movie_ids)}
    n_movies = len(index)
    log.info("Movie IDs: %d (min=%s, max=%s)", n_movies, movie_ids[0], movie_ids[-1])

    index_path = args.output / "movie_id_index.json"
    with open(index_path, "w") as f:
        json.dump(index, f, separators=(",", ":"))

    size_mb = index_path.stat().st_size / (1024 * 1024)
    log.info("Saved %s (%.1f MB)", index_path, size_mb)

    # --- Verify pipeline outputs ---
    log.info("=== Verifying pipeline outputs ===")
    all_ok = True

    for fname in EXPECTED_NPY:
        fpath = args.output / fname
        if not fpath.exists():
            log.warning("  MISSING: %s", fname)
            all_ok = False
            continue
        arr = np.load(fpath)
        rows = arr.shape[0]
        size = fpath.stat().st_size / (1024 * 1024)
        status = "OK" if rows == n_movies else f"MISMATCH (expected {n_movies})"
        if rows != n_movies:
            all_ok = False
        log.info("  %-30s %s  rows=%d  %.1f MB", fname, status, rows, size)

    # Check JSON maps
    for fname in ["genre_mood_map.json", "keyword_mood_map.json"]:
        fpath = args.output / fname
        if fpath.exists():
            with open(fpath) as f:
                data = json.load(f)
            log.info("  %-30s OK  entries=%d", fname, len(data))
        else:
            log.warning("  MISSING: %s", fname)
            all_ok = False

    # Check SVD models
    for fname in ["keyword_svd.pkl", "director_svd.pkl", "actor_svd.pkl"]:
        fpath = args.output / fname
        status = "OK" if fpath.exists() else "MISSING"
        if not fpath.exists():
            all_ok = False
        log.info("  %-30s %s", fname, status)

    if all_ok:
        log.info("=== All pipeline outputs verified ===")
    else:
        log.warning("=== Some outputs missing or inconsistent ===")

    return 0


if __name__ == "__main__":
    sys.exit(main())
