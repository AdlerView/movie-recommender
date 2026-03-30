"""Verify all pipeline outputs exist and have consistent row counts. See PIPELINE.md."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

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


def run(output_dir: Path) -> bool:
    """Verify pipeline outputs. Returns True if all OK."""
    index_path = output_dir / "movie_id_index.json"
    if not index_path.exists():
        log.error("movie_id_index.json not found — run index first")
        return False

    with open(index_path) as f:
        index = json.load(f)
    n_movies = len(index)
    log.info("Reference: movie_id_index.json (%d movies)", n_movies)

    log.info("=== Verifying pipeline outputs ===")
    all_ok = True

    for fname in EXPECTED_NPY:
        fpath = output_dir / fname
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

    for fname, fdir in [
        ("keyword_mood_map.json", output_dir),
        ("genre_mood_map.json", output_dir.parent / "source"),
    ]:
        fpath = fdir / fname
        if fpath.exists():
            with open(fpath) as f:
                data = json.load(f)
            log.info("  %-30s OK  entries=%d", fname, len(data))
        else:
            log.warning("  MISSING: %s", fname)
            all_ok = False

    for fname in ["keyword_svd.pkl", "director_svd.pkl", "actor_svd.pkl"]:
        fpath = output_dir / fname
        status = "OK" if fpath.exists() else "MISSING"
        if not fpath.exists():
            all_ok = False
        log.info("  %-30s %s", fname, status)

    if all_ok:
        log.info("=== All pipeline outputs verified ===")
    else:
        log.warning("=== Some outputs missing or inconsistent ===")

    return all_ok
