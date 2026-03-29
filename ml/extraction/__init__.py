"""Offline feature extraction. Pipeline: see EXTRACTION.md."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def load_movie_ids(conn) -> tuple[np.ndarray, dict[int, int]]:
    """Load canonical movie ID ordering (shared across pipeline stages)."""
    df = pd.read_sql_query("SELECT id FROM movies ORDER BY id", conn)
    ids = df["id"].to_numpy()
    id_to_row = {int(mid): i for i, mid in enumerate(ids)}
    log.info("Loaded %d movie IDs (min=%d, max=%d)", len(ids), ids.min(), ids.max())
    return ids, id_to_row
