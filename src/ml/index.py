"""Build movie_id_index.json from tmdb.sqlite. See PIPELINE.md."""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)


def run(db_path: Path, output_dir: Path) -> None:
    """Build movie ID index."""
    log.info("=== Building movie ID index ===")
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT id FROM movies ORDER BY id")
    movie_ids = [row[0] for row in cursor]
    conn.close()

    index = {str(mid): i for i, mid in enumerate(movie_ids)}
    log.info("Movie IDs: %d (min=%s, max=%s)", len(index), movie_ids[0], movie_ids[-1])

    index_path = output_dir / "movie_id_index.json"
    with open(index_path, "w") as f:
        json.dump(index, f, separators=(",", ":"))

    size_mb = index_path.stat().st_size / (1024 * 1024)
    log.info("Saved %s (%.1f MB)", index_path, size_mb)
