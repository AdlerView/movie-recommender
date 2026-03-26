#!/usr/bin/env python3
"""Quality score pipeline (Stage 3).

Computes a Bayesian average quality score for each movie, correcting
for vote count bias. Movies with very few votes are pulled toward the
global average, preventing a film with 1 vote and 10.0 average from
outranking a well-established film with 10,000 votes and 8.5 average.

Formula (Bayesian average):
    m = median(all vote_counts where > 0)   # ~14 for TMDB
    C = mean(all vote_averages where > 0)   # ~6.0 for TMDB
    quality(movie) = (v * R + m * C) / (v + m)

    where v = vote_count, R = vote_average for the movie.

    At v >> m: quality ≈ R (own average dominates)
    At v << m: quality ≈ C (pulled to global average)
    At v = 0:  quality = C (no information, assume average)

Output is normalized to [0, 1] for use in the scoring formula.

Beyond-course extension: Bayesian averaging is not taught in the
course but solves a real data quality problem in TMDB vote data.

Data flow:
    store/tmdb.sqlite (movies.vote_average, movies.vote_count)
        → Bayesian average per movie (numpy vectorized)
        → normalize to [0, 1]
        → store/quality_scores.npy (1.17M × 1, float32)

Row ordering: SELECT id FROM movies ORDER BY id (same as Stage 1).
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def main() -> int:
    """Run the quality score pipeline.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Compute Bayesian average quality scores for all movies.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("store/tmdb.sqlite"),
        help="Path to TMDB SQLite database (default: store/tmdb.sqlite)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("store"),
        help="Output directory for quality_scores.npy (default: store/)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        log.error("Database not found: %s", args.db)
        return 1

    args.output.mkdir(parents=True, exist_ok=True)

    # --- Load vote data ---
    log.info("=== Loading vote data from %s ===", args.db)
    conn = sqlite3.connect(args.db)
    df = pd.read_sql_query(
        "SELECT id, vote_average, vote_count FROM movies ORDER BY id",
        conn,
    )
    conn.close()
    log.info("Loaded %d movies", len(df))

    # Handle NULLs: treat as zero votes / zero average
    vote_avg = df["vote_average"].fillna(0.0).to_numpy(dtype=np.float64)
    vote_cnt = df["vote_count"].fillna(0).to_numpy(dtype=np.float64)

    # --- Compute global priors (from movies with at least 1 vote) ---
    has_votes = vote_cnt > 0
    m = float(np.median(vote_cnt[has_votes]))
    c = float(np.mean(vote_avg[has_votes]))
    log.info("Global priors: m (median vote count) = %.1f, C (mean vote average) = %.4f", m, c)
    log.info("Movies with votes: %d, without: %d", has_votes.sum(), (~has_votes).sum())

    # --- Bayesian average (vectorized) ---
    quality = (vote_cnt * vote_avg + m * c) / (vote_cnt + m)
    log.info(
        "Raw quality scores: min=%.4f, max=%.4f, mean=%.4f, median=%.4f",
        quality.min(), quality.max(), quality.mean(), np.median(quality),
    )

    # --- Normalize to [0, 1] ---
    q_min = quality.min()
    q_max = quality.max()
    quality_normalized = ((quality - q_min) / (q_max - q_min)).astype(np.float32)
    quality_normalized = quality_normalized.reshape(-1, 1)
    log.info("Normalized: shape=%s, range=[%.4f, %.4f]", quality_normalized.shape, quality_normalized.min(), quality_normalized.max())

    # --- Save ---
    out_path = args.output / "quality_scores.npy"
    np.save(out_path, quality_normalized)
    size_mb = out_path.stat().st_size / (1024 * 1024)
    log.info("Saved %s (%.1f MB)", out_path, size_mb)

    # --- Spot checks ---
    log.info("=== Spot checks ===")
    id_to_row = {int(mid): i for i, mid in enumerate(df["id"])}
    checks = [
        (550, "Fight Club"),
        (680, "Pulp Fiction"),
        (155, "The Dark Knight"),
        (19404, "Dilwale Dulhania Le Jayenge"),
    ]
    for mid, title in checks:
        if mid in id_to_row:
            row = id_to_row[mid]
            log.info(
                "  %-35s votes=%5d  avg=%.1f  quality=%.4f",
                title, int(vote_cnt[row]), vote_avg[row], float(quality_normalized[row, 0]),
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
