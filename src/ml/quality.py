"""Quality score pipeline (Stage 3). See SCORING.md (Quality Score section)."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def run(db_path: Path, output_dir: Path) -> None:
    """Compute Bayesian average quality scores for all movies."""
    conn = sqlite3.connect(db_path)
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
    out_path = output_dir / "quality_scores.npy"
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

