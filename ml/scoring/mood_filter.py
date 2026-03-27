"""Local mood filter against precomputed mood scores.

Filters TMDB API candidates by mood using the precomputed mood_scores.npy
array (1.17M movies x 7 moods). This is the only filter that runs locally
— all other discovery filters are handled by the TMDB API.

The filter applies a threshold with stepwise fallback to prevent empty
results for rare moods like "Disgusted":
    1. Keep candidates where selected mood score > 0.3
    2. If fewer than 20 remain, lower to 0.2
    3. If still fewer than 20, lower to 0.1
    4. If still fewer than 20, lower to 0.0 (= no mood filter)

When multiple moods are selected, the average across selected moods is
used as the filter criterion.

Data flow:
    candidate movie IDs (from TMDB API discover response)
    + selected moods (from Discover page mood pills)
    + mood_scores.npy (via get_model() singleton)
        → filtered list of movie IDs that match the mood criteria
"""
from __future__ import annotations

import logging
from typing import Final

import numpy as np

from ml.scoring.user_profile import MOOD_IDX, get_model

log = logging.getLogger(__name__)

# Threshold settings (from SCORING.md)
_INITIAL_THRESHOLD: Final[float] = 0.3
_FALLBACK_THRESHOLDS: Final[list[float]] = [0.2, 0.1, 0.0]
_MIN_RESULTS: Final[int] = 20


def filter_by_mood(
    candidate_ids: list[int],
    selected_moods: list[str],
    min_results: int = _MIN_RESULTS,
) -> list[int]:
    """Filter candidate movies by mood scores with threshold fallback.

    Looks up precomputed mood scores for each candidate and keeps only
    those above the threshold for the selected moods. If too few results
    remain, the threshold is lowered stepwise until at least min_results
    candidates pass or the threshold reaches 0.

    When multiple moods are selected, the average of the selected mood
    scores is used as the filter criterion.

    Args:
        candidate_ids: Movie IDs from the TMDB API discover response.
        selected_moods: Mood names selected by the user
            (e.g., ["Happy", "Afraid"]). Must be non-empty.
        min_results: Minimum number of results before fallback triggers.

    Returns:
        Filtered list of movie IDs, preserving the original order.
        Returns the full candidate list if no valid moods are selected.
    """
    if not selected_moods or not candidate_ids:
        return candidate_ids

    # Resolve mood names to column indices
    mood_indices = [MOOD_IDX[m] for m in selected_moods if m in MOOD_IDX]
    if not mood_indices:
        return candidate_ids

    model = get_model()
    index = model.movie_id_index

    # Look up row indices and mood scores for all candidates
    rows: list[int | None] = []
    for mid in candidate_ids:
        rows.append(index.get(str(mid)))

    # Compute average mood score across selected moods for each candidate
    scores = np.zeros(len(candidate_ids), dtype=np.float32)
    for i, row in enumerate(rows):
        if row is not None:
            # Average of selected mood columns for this movie
            scores[i] = model.mood_scores[row, mood_indices].mean()
        # Movies not in the index get score 0 (filtered out unless threshold = 0)

    # Apply threshold with fallback
    threshold = _INITIAL_THRESHOLD
    filtered = [mid for mid, s in zip(candidate_ids, scores) if s > threshold]

    for fallback in _FALLBACK_THRESHOLDS:
        if len(filtered) >= min_results:
            break
        threshold = fallback
        filtered = [mid for mid, s in zip(candidate_ids, scores) if s > threshold]

    # At threshold 0.0, include everything with score > 0
    # If still not enough, return all candidates (mood filter disabled)
    if len(filtered) < min_results:
        log.info(
            "Mood filter disabled: only %d/%d candidates above threshold 0.0",
            len(filtered), len(candidate_ids),
        )
        return candidate_ids

    log.info(
        "Mood filter: %d/%d candidates pass (moods=%s, threshold=%.1f)",
        len(filtered), len(candidate_ids), selected_moods, threshold,
    )
    return filtered
