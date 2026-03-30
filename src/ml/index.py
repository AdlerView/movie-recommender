#!/usr/bin/env python3
"""Build movie_id_index.json from tmdb.sqlite. See PIPELINE.md."""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def main() -> int:
    """Build movie ID index."""
    parser = argparse.ArgumentParser(
        description="Build movie_id_index.json from tmdb.sqlite.",
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

    args.output.mkdir(parents=True, exist_ok=True)

    log.info("=== Building movie ID index ===")
    conn = sqlite3.connect(args.db)
    cursor = conn.execute("SELECT id FROM movies ORDER BY id")
    movie_ids = [row[0] for row in cursor]
    conn.close()

    # Bidirectional mapping: movie_id (str) → row_index (int)
    index = {str(mid): i for i, mid in enumerate(movie_ids)}
    log.info("Movie IDs: %d (min=%s, max=%s)", len(index), movie_ids[0], movie_ids[-1])

    index_path = args.output / "movie_id_index.json"
    with open(index_path, "w") as f:
        json.dump(index, f, separators=(",", ":"))

    size_mb = index_path.stat().st_size / (1024 * 1024)
    log.info("Saved %s (%.1f MB)", index_path, size_mb)

    return 0


if __name__ == "__main__":
    sys.exit(main())
