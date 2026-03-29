#!/usr/bin/env python3
"""Mood prediction pipeline (Stage 2): 4 signals combined per movie. See CLASSIFICATION.md."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

# Fully offline — see CLASSIFICATION.md (Signal 3)
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import numpy as np
import pandas as pd
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# 7 canonical mood columns in fixed order
MOODS = ["happy", "interested", "surprised", "sad", "disgusted", "afraid", "angry"]
MOOD_IDX = {m: i for i, m in enumerate(MOODS)}

# Emotion classifier → our 7 moods (direct 7-to-7 mapping).
# neutral → interested: factual/informational text = thought-provoking content
EMOTION_TO_MOOD = {
    "joy": "happy",
    "neutral": "interested",
    "anger": "angry",
    "disgust": "disgusted",
    "fear": "afraid",
    "sadness": "sad",
    "surprise": "surprised",
}


def load_movie_ids(conn: sqlite3.Connection) -> tuple[np.ndarray, dict[int, int]]:
    """Load canonical movie ID ordering (shared across pipeline stages)."""
    df = pd.read_sql_query("SELECT id FROM movies ORDER BY id", conn)
    ids = df["id"].to_numpy()
    id_to_row = {int(mid): i for i, mid in enumerate(ids)}
    log.info("Loaded %d movie IDs", len(ids))
    return ids, id_to_row


def compute_genre_signal(
    conn: sqlite3.Connection,
    id_to_row: dict[int, int],
    n_movies: int,
    genre_map: dict,
) -> np.ndarray:
    """Signal 1: genre→mood scores. Mapping: see CLASSIFICATION.md."""
    log.info("--- Signal 1: Genre → Mood ---")

    # Load genre names for ID lookup
    genres_df = pd.read_sql_query("SELECT id, name FROM genres", conn)
    genre_id_to_name = dict(zip(genres_df["id"], genres_df["name"]))

    # Load movie-genre assignments
    mg_df = pd.read_sql_query("SELECT movie_id, genre_id FROM movie_genres", conn)
    log.info("Loaded %d movie-genre pairs", len(mg_df))

    scores = np.zeros((n_movies, 7), dtype=np.float64)
    counts = np.zeros(n_movies, dtype=np.int32)

    for mid, gid in tqdm(
        zip(mg_df["movie_id"], mg_df["genre_id"]),
        total=len(mg_df), desc="Genre signal", unit="pair",
    ):
        if mid not in id_to_row:
            continue
        row = id_to_row[mid]
        genre_name = genre_id_to_name.get(gid)
        if genre_name and genre_name in genre_map:
            mood_weights = genre_map[genre_name]
            for mood, weight in mood_weights.items():
                if mood in MOOD_IDX:
                    scores[row, MOOD_IDX[mood]] += weight
            counts[row] += 1

    # Average across genres (avoid division by zero)
    mask = counts > 0
    scores[mask] /= counts[mask, np.newaxis]

    nonzero = int(mask.sum())
    log.info("Genre signal: %d movies with genres, %d without", nonzero, n_movies - nonzero)
    return scores.astype(np.float32)


def compute_keyword_signal(
    conn: sqlite3.Connection,
    id_to_row: dict[int, int],
    n_movies: int,
    keyword_map: dict,
) -> np.ndarray:
    """Signal 2: keyword→mood scores from keyword_mood_map.json."""
    log.info("--- Signal 2: Keyword → Mood ---")

    mk_df = pd.read_sql_query(
        "SELECT mk.movie_id, k.name FROM movie_keywords mk "
        "JOIN keywords k ON mk.keyword_id = k.id",
        conn,
    )
    log.info("Loaded %d movie-keyword pairs with names", len(mk_df))

    scores = np.zeros((n_movies, 7), dtype=np.float64)
    counts = np.zeros(n_movies, dtype=np.int32)

    for mid, kw_name in tqdm(
        zip(mk_df["movie_id"], mk_df["name"]),
        total=len(mk_df), desc="Keyword signal", unit="pair",
    ):
        if mid not in id_to_row:
            continue
        if kw_name not in keyword_map:
            continue
        row = id_to_row[mid]
        mood_weights = keyword_map[kw_name]
        for mood, weight in mood_weights.items():
            if mood in MOOD_IDX:
                scores[row, MOOD_IDX[mood]] += weight
        counts[row] += 1

    mask = counts > 0
    scores[mask] /= counts[mask, np.newaxis]

    nonzero = int(mask.sum())
    log.info("Keyword signal: %d movies with keyword moods, %d without", nonzero, n_movies - nonzero)
    return scores.astype(np.float32)


def compute_emotion_signal(
    conn: sqlite3.Connection,
    id_to_row: dict[int, int],
    n_movies: int,
    batch_size: int,
    source: str,
) -> np.ndarray:
    """Emotion classifier on text (overview or reviews). See CLASSIFICATION.md."""
    from transformers import pipeline as hf_pipeline

    log.info("--- Signal: Emotion classifier on %s ---", source)

    # Load texts
    if source == "overview":
        df = pd.read_sql_query(
            "SELECT id AS movie_id, overview, tagline FROM movies ORDER BY id", conn,
        )
        # Concatenate overview + tagline
        texts = []
        movie_ids = []
        for _, row in df.iterrows():
            mid = row["movie_id"]
            if mid not in id_to_row:
                continue
            overview = row["overview"] if pd.notna(row["overview"]) else ""
            tagline = row["tagline"] if pd.notna(row["tagline"]) else ""
            text = f"{overview} {tagline}".strip()
            if text:
                texts.append(text)
                movie_ids.append(mid)
    elif source == "reviews":
        df = pd.read_sql_query(
            "SELECT movie_id, content FROM movie_reviews", conn,
        )
        # Group reviews by movie, concatenate (truncated)
        grouped = {}
        for mid, content in zip(df["movie_id"], df["content"]):
            if mid not in id_to_row:
                continue
            if pd.notna(content) and content.strip():
                grouped.setdefault(mid, []).append(content.strip()[:500])
        texts = [" ".join(reviews) for reviews in grouped.values()]
        movie_ids = list(grouped.keys())
    else:
        raise ValueError(f"Unknown source: {source}")

    log.info("Texts to classify: %d", len(texts))

    if not texts:
        return np.zeros((n_movies, 7), dtype=np.float32)

    # Load emotion classifier (fully offline, no network requests)
    log.info("Loading emotion classifier (j-hartmann/emotion-english-distilroberta-base)")
    classifier = hf_pipeline(
        "text-classification",
        model="j-hartmann/emotion-english-distilroberta-base",
        top_k=None,
        truncation=True,
        max_length=512,
        device="mps",
        local_files_only=True,
    )

    # Run in batches with progress bar
    scores = np.zeros((n_movies, 7), dtype=np.float64)
    n_batches = (len(texts) + batch_size - 1) // batch_size

    for batch_idx in tqdm(range(n_batches), desc=f"Emotion ({source})", unit="batch"):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(texts))
        batch_texts = texts[start:end]
        batch_ids = movie_ids[start:end]

        results = classifier(batch_texts)

        for mid, result in zip(batch_ids, results):
            row = id_to_row[mid]
            # result is a list of {label, score} dicts for all 7 classes
            for item in result:
                label = item["label"]
                if label in EMOTION_TO_MOOD:
                    mood = EMOTION_TO_MOOD[label]
                    scores[row, MOOD_IDX[mood]] = item["score"]

    nonzero = int((scores.sum(axis=1) > 0).sum())
    log.info("Emotion signal (%s): %d movies scored", source, nonzero)
    return scores.astype(np.float32)


def combine_signals(
    genre: np.ndarray,
    keyword: np.ndarray,
    overview: np.ndarray,
    reviews: np.ndarray,
    n_movies: int,
) -> np.ndarray:
    """Combine 4 signals with dynamic weights (see CLASSIFICATION.md)."""
    log.info("--- Combining 4 signals ---")

    has_reviews = reviews.sum(axis=1) > 0
    has_overview = overview.sum(axis=1) > 0

    combined = np.zeros((n_movies, 7), dtype=np.float64)

    # Case 1: has reviews (and implicitly overview)
    mask_r = has_reviews
    combined[mask_r] = (
        0.50 * reviews[mask_r]
        + 0.20 * overview[mask_r]
        + 0.20 * genre[mask_r]
        + 0.10 * keyword[mask_r]
    )

    # Case 2: has overview but no reviews
    mask_o = ~has_reviews & has_overview
    combined[mask_o] = (
        0.50 * overview[mask_o]
        + 0.30 * genre[mask_o]
        + 0.20 * keyword[mask_o]
    )

    # Case 3: no overview, no reviews (genre + keyword only)
    mask_g = ~has_reviews & ~has_overview
    combined[mask_g] = (
        0.60 * genre[mask_g]
        + 0.40 * keyword[mask_g]
    )

    log.info(
        "Signal coverage: reviews=%d, overview-only=%d, genre+keyword-only=%d",
        int(mask_r.sum()), int(mask_o.sum()), int(mask_g.sum()),
    )

    return combined.astype(np.float32)


def main() -> int:
    """Run mood prediction pipeline."""
    parser = argparse.ArgumentParser(
        description="Predict mood scores for all movies from 4 signals.",
    )
    parser.add_argument(
        "--db", type=Path, default=Path("data/input/tmdb.sqlite"),
        help="Path to TMDB SQLite database (default: data/input/tmdb.sqlite)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/output"),
        help="Output directory for mood_scores.npy (default: data/output/)",
    )
    parser.add_argument(
        "--genre-map", type=Path, default=Path("data/input/genre_mood_map.json"),
        help="Path to genre mood map JSON (default: data/input/genre_mood_map.json)",
    )
    parser.add_argument(
        "--keyword-map", type=Path, default=Path("data/output/keyword_mood_map.json"),
        help="Path to keyword mood map JSON (default: data/output/keyword_mood_map.json)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=64,
        help="Batch size for emotion classifier (default: 64)",
    )
    parser.add_argument(
        "--skip-emotion", action="store_true",
        help="Skip emotion classifier (use only genre + keyword signals)",
    )
    args = parser.parse_args()

    # Validate inputs
    for path, name in [(args.db, "database"), (args.genre_map, "genre map"), (args.keyword_map, "keyword map")]:
        if not path.exists():
            log.error("%s not found: %s", name.capitalize(), path)
            return 1

    args.output.mkdir(parents=True, exist_ok=True)

    # Load mood maps
    log.info("=== Loading mood maps ===")
    with open(args.genre_map) as f:
        genre_map = json.load(f)
    log.info("Genre map: %d entries", len(genre_map))

    with open(args.keyword_map) as f:
        keyword_map = json.load(f)
    log.info("Keyword map: %d entries", len(keyword_map))

    # Load movie IDs
    conn = sqlite3.connect(args.db)
    movie_ids, id_to_row = load_movie_ids(conn)
    n_movies = len(movie_ids)

    # --- Signal 1: Genre ---
    genre_signal = compute_genre_signal(conn, id_to_row, n_movies, genre_map)

    # --- Signal 2: Keywords ---
    keyword_signal = compute_keyword_signal(conn, id_to_row, n_movies, keyword_map)

    # --- Signals 3+4: Emotion classifier ---
    if args.skip_emotion:
        log.info("=== Skipping emotion classifier (--skip-emotion) ===")
        overview_signal = np.zeros((n_movies, 7), dtype=np.float32)
        review_signal = np.zeros((n_movies, 7), dtype=np.float32)
    else:
        log.info("=== Signal 3: Emotion on overviews ===")
        overview_signal = compute_emotion_signal(conn, id_to_row, n_movies, args.batch_size, "overview")

        log.info("=== Signal 4: Emotion on reviews ===")
        review_signal = compute_emotion_signal(conn, id_to_row, n_movies, args.batch_size, "reviews")

    conn.close()

    # --- Combine signals ---
    mood_scores = combine_signals(genre_signal, keyword_signal, overview_signal, review_signal, n_movies)

    # --- Save ---
    out_path = args.output / "mood_scores.npy"
    np.save(out_path, mood_scores)
    size_mb = out_path.stat().st_size / (1024 * 1024)
    log.info("Saved %s: shape=%s, %.1f MB", out_path, mood_scores.shape, size_mb)

    # --- Spot checks ---
    log.info("=== Spot checks (top mood per movie) ===")
    checks = [
        (550, "Fight Club"),
        (680, "Pulp Fiction"),
        (155, "The Dark Knight"),
        (120, "The Lord of the Rings: FOTR"),
        (27205, "Inception"),
    ]
    for mid, title in checks:
        if mid in id_to_row:
            row = id_to_row[mid]
            scores = mood_scores[row]
            top_mood = MOODS[int(np.argmax(scores))]
            top_score = float(scores.max())
            moods_str = ", ".join(f"{MOODS[i]}={scores[i]:.2f}" for i in range(7) if scores[i] > 0.1)
            log.info("  %-35s top=%s (%.2f)  [%s]", title, top_mood, top_score, moods_str)

    # --- Summary ---
    log.info("=== Summary ===")
    has_any = (mood_scores.sum(axis=1) > 0).sum()
    log.info("Movies with mood scores: %d / %d (%.1f%%)", has_any, n_movies, has_any / n_movies * 100)
    for i, mood in enumerate(MOODS):
        mean_val = mood_scores[:, i].mean()
        max_val = mood_scores[:, i].max()
        log.info("  %-12s mean=%.4f  max=%.4f", mood, mean_val, max_val)

    return 0


if __name__ == "__main__":
    sys.exit(main())
