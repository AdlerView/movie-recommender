#!/usr/bin/env python3
"""Verify all pipeline outputs exist and have consistent row counts. See PIPELINE.md."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

EXPECTED_NPY = [
    "keyword_svd_vectors.npy",
    "director_svd_vectors.npy",
    "actor_svd_vectors.npy",
    "genre_vectors.npy",
    "decade_vectors.npy",
    "language_vectors.npy",
    "runtime_normalized.npy",
    "popularity_normalized.npy",
    "mood_scores.npy",
    "quality_scores.npy",
]


def main() -> int:
    """Verify pipeline outputs against movie_id_index.json."""
    parser = argparse.ArgumentParser(
        description="Verify pipeline output files for existence and row-count consistency.",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/models"),
        help="Output directory (default: data/models/)",
    )
    args = parser.parse_args()

    # Load movie_id_index.json as row-count reference
    index_path = args.output / "movie_id_index.json"
    if not index_path.exists():
        log.error("movie_id_index.json not found — run index.py first")
        return 1

    with open(index_path) as f:
        index = json.load(f)
    n_movies = len(index)
    log.info("Reference: movie_id_index.json (%d movies)", n_movies)

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
    for fname, fdir in [
        ("keyword_mood_map.json", args.output),
        ("genre_mood_map.json", args.output.parent / "source"),
    ]:
        fpath = fdir / fname
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
