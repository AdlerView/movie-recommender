#!/usr/bin/env python3
"""ML pipeline runner. Single entry point for all offline stages."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DB_PATH = Path("data/source/tmdb.sqlite")
OUTPUT_DIR = Path("data/models")


def main() -> int:
    """Run the full ML pipeline or individual stages."""
    parser = argparse.ArgumentParser(description="ML pipeline runner.")
    parser.add_argument(
        "stages", nargs="*",
        default=["features", "classifier", "moods", "quality", "index", "verify"],
        help="Stages to run (default: all). Options: features, classifier, moods, quality, index, verify",
    )
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    if not args.db.exists():
        log.error("Database not found: %s", args.db)
        return 1

    args.output.mkdir(parents=True, exist_ok=True)

    for stage in args.stages:
        log.info("=" * 60)
        log.info("STAGE: %s", stage)
        log.info("=" * 60)

        if stage == "features":
            from src.ml.features import run
            run(args.db, args.output)

        elif stage == "classifier":
            from src.ml.classifier import run
            run(db_path=args.db)

        elif stage == "moods":
            from src.ml.moods import run
            run(args.db, args.output)

        elif stage == "quality":
            from src.ml.quality import run
            run(args.db, args.output)

        elif stage == "index":
            from src.ml.index import run
            run(args.db, args.output)

        elif stage == "verify":
            from src.ml.verify import run
            if not run(args.output):
                return 1

        else:
            log.error("Unknown stage: %s", stage)
            return 1

    log.info("=" * 60)
    log.info("Pipeline complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
