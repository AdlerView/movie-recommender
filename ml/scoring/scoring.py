"""11-signal cosine similarity scoring. Signals, weights, architecture: see SCORING.md."""
from __future__ import annotations

import logging
from typing import Final

import numpy as np

from ml.scoring.arrays import MOOD_IDX, MOODS, get_model
from ml.scoring.profile import UserProfile

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dynamic weight table (from SCORING.md)
# ---------------------------------------------------------------------------
# Columns: keyword, mood, genre, director, actor, decade, language, runtime, popularity, quality, contra
# Each row sums to 1.0. Rebalanced: genre↑, popularity new, director↓, keyword↓.

_WEIGHT_TABLE: Final[dict[str, np.ndarray]] = {
    #              kw    mood  genre dir   act   dec   lang  run   pop   qual  contra
    "cold":  np.array([0.00, 0.35, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.65, 0.00], dtype=np.float32),
    "few":   np.array([0.06, 0.20, 0.06, 0.04, 0.03, 0.02, 0.01, 0.01, 0.04, 0.50, 0.03], dtype=np.float32),
    "mid":   np.array([0.10, 0.18, 0.12, 0.07, 0.06, 0.04, 0.02, 0.02, 0.07, 0.22, 0.10], dtype=np.float32),
    "full":  np.array([0.12, 0.18, 0.15, 0.07, 0.07, 0.03, 0.03, 0.03, 0.08, 0.10, 0.14], dtype=np.float32),
}

# Signal names in the same order as the weight columns (11 signals)
SIGNAL_NAMES: Final[list[str]] = [
    "keyword", "mood", "genre", "director", "actor", "decade",
    "language", "runtime", "popularity", "quality", "contra",
]


def get_weights(rating_count: int) -> np.ndarray:
    """Select weight vector for rating count tier (see SCORING.md)."""
    if rating_count == 0:
        return _WEIGHT_TABLE["cold"]
    if rating_count < 10:
        return _WEIGHT_TABLE["few"]
    if rating_count < 50:
        return _WEIGHT_TABLE["mid"]
    return _WEIGHT_TABLE["full"]


# ---------------------------------------------------------------------------
# Batch cosine similarity
# ---------------------------------------------------------------------------

def _batch_cosine_sim(user_vec: np.ndarray, candidate_matrix: np.ndarray) -> np.ndarray:
    """Batch cosine similarity: user vector vs candidate matrix."""
    user_norm = np.linalg.norm(user_vec)
    if user_norm < 1e-9:
        return np.zeros(candidate_matrix.shape[0], dtype=np.float32)

    # dot product: (n, dim) @ (dim,) → (n,)
    dots = candidate_matrix @ user_vec
    # candidate norms: (n,)
    cand_norms = np.linalg.norm(candidate_matrix, axis=1)
    # Avoid division by zero for zero-norm candidates
    cand_norms = np.maximum(cand_norms, 1e-9)

    return (dots / (user_norm * cand_norms)).astype(np.float32)


# ---------------------------------------------------------------------------
# Score candidates
# ---------------------------------------------------------------------------

def score_candidates(
    profile: UserProfile,
    candidate_ids: list[int],
    selected_moods: list[str] | None = None,
) -> list[tuple[int, float]]:
    """Score candidates against user profile. 11 signals, dynamic weights. See SCORING.md."""
    if not candidate_ids:
        return []

    model = get_model()
    index = model.movie_id_index

    # Resolve candidate IDs to row indices, track which are found
    row_indices: list[int] = []
    valid_ids: list[int] = []
    missing_ids: list[int] = []

    for mid in candidate_ids:
        row = index.get(str(mid))
        if row is not None:
            row_indices.append(row)
            valid_ids.append(mid)
        else:
            missing_ids.append(mid)

    if not row_indices:
        # No candidates found in precomputed arrays — return empty
        return [(mid, 0.0) for mid in candidate_ids]

    rows = np.array(row_indices)
    n = len(rows)
    weights = get_weights(profile.rating_count)

    # All 11 signals — see SCORING.md for details
    keyword_sim = _batch_cosine_sim(profile.keyword_vec, model.keyword_svd[rows])

    # Mood: explicit (avg of selected columns) or implicit (dot with mood frequency)
    candidate_moods = model.mood_scores[rows]
    if selected_moods:
        mood_indices = [MOOD_IDX[m] for m in selected_moods if m in MOOD_IDX]
        mood_match = candidate_moods[:, mood_indices].mean(axis=1) if mood_indices else np.zeros(n, dtype=np.float32)
    else:
        mood_match = candidate_moods @ profile.implicit_mood

    genre_sim = _batch_cosine_sim(profile.genre_vec, model.genre_vectors[rows])
    director_sim = _batch_cosine_sim(profile.director_vec, model.director_svd[rows])
    actor_sim = _batch_cosine_sim(profile.actor_vec, model.actor_svd[rows])
    decade_sim = _batch_cosine_sim(profile.decade_vec, model.decade_vectors[rows])
    language_sim = _batch_cosine_sim(profile.language_vec, model.language_vectors[rows])

    # Runtime + popularity: distance-based (1 - |user_pref - candidate|)
    candidate_runtimes = model.runtime_normalized[rows].flatten()
    runtime_sim = (1.0 - np.abs(profile.runtime_pref - candidate_runtimes)).astype(np.float32)
    candidate_pop = model.popularity_normalized[rows].flatten()
    popularity_sim = (1.0 - np.abs(profile.popularity_pref - candidate_pop)).astype(np.float32)

    quality = model.quality_scores[rows].flatten()

    # Contra: negate so similar-to-disliked hurts the score
    contra_penalty = -_batch_cosine_sim(profile.contra_vec, model.keyword_svd[rows])

    # Stack and compute weighted sum
    signals = np.column_stack([
        keyword_sim, mood_match, genre_sim, director_sim, actor_sim,
        decade_sim, language_sim, runtime_sim, popularity_sim,
        quality, contra_penalty,
    ])
    final_scores = (signals * weights).sum(axis=1)

    # --- Build result list ---
    results: list[tuple[int, float]] = [
        (mid, float(score)) for mid, score in zip(valid_ids, final_scores)
    ]

    # Movies not in the index get a fallback score (quality-only from API data)
    for mid in missing_ids:
        results.append((mid, 0.0))

    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)

    log.info(
        "Scored %d candidates (%d found, %d missing), tier=%s",
        len(candidate_ids), len(valid_ids), len(missing_ids),
        "cold" if profile.rating_count == 0
        else "few" if profile.rating_count < 10
        else "mid" if profile.rating_count < 50
        else "full",
    )

    return results
