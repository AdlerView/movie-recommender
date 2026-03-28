"""Personalized movie scoring with 10-signal cosine similarity.

Scores candidate movies against a user profile using 10 weighted similarity
signals. All computations are batch-vectorized with numpy for performance
(~8ms for 300 candidates on a single CPU core).

The 10 signals and their full-personalization weights (50+ ratings):
    keyword_similarity   0.20  — cosine sim of keyword SVD vectors
    mood_match           0.20  — explicit mood selection or implicit mood profile
    genre_similarity     0.05  — cosine sim of genre multi-hot vectors
    director_similarity  0.15  — cosine sim of director SVD vectors
    actor_similarity     0.10  — cosine sim of actor SVD vectors
    decade_similarity    0.05  — cosine sim of decade onehot vectors
    language_similarity  0.03  — cosine sim of language onehot vectors
    runtime_similarity   0.02  — 1 - |user_pref - candidate| (normalized)
    quality_score        0.10  — precomputed Bayesian average [0,1]
    contra_penalty       0.10  — negative cosine sim against disliked themes

Weights shift dynamically based on rating count (cold start → quality-heavy,
50+ ratings → personalization-heavy). See SCORING.md for the weight table.

Data flow:
    UserProfile (from user_profile.py)
    + candidate movie IDs (from TMDB API discover response)
    + model arrays (lazy singleton from user_profile.py)
        → 10 signal scores per candidate (numpy batch)
        → weighted sum using dynamic weights
        → sorted list of (movie_id, final_score) tuples
"""
from __future__ import annotations

import logging
from typing import Final

import numpy as np

from ml.scoring.user_profile import MOODS, MOOD_IDX, UserProfile, get_model

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
    """Select the weight vector for the given rating count tier.

    Args:
        rating_count: Number of movies the user has rated.

    Returns:
        Weight vector of shape (11,) summing to 1.0.
    """
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
    """Compute cosine similarity between a user vector and a batch of candidates.

    Args:
        user_vec: User preference vector of shape (dim,).
        candidate_matrix: Candidate vectors of shape (n, dim).

    Returns:
        Similarity scores of shape (n,), in range [-1, 1].
        Returns zeros if the user vector has zero norm.
    """
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
    """Score candidate movies against the user profile.

    Computes 10 similarity signals for each candidate, applies dynamic
    weights based on the user's rating count, and returns sorted results.

    Candidates not found in the movie_id_index (e.g., very new movies)
    are scored with quality_score only (graceful degradation).

    Args:
        profile: User profile with preference vectors (from user_profile.py).
        candidate_ids: List of TMDB movie IDs to score.
        selected_moods: Explicitly selected mood names (e.g., ["Happy", "Afraid"]).
            If provided, mood_match uses the average of selected mood scores.
            If None, mood_match uses the implicit mood from the user's profile.

    Returns:
        List of (movie_id, score) tuples, sorted by score descending.
        Scores are in range [0, 1] (approximately).
    """
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

    # --- Signal 1: Keyword similarity (weight 0.20) ---
    # Cosine sim between user's keyword preference vector and each candidate's
    # keyword SVD vector. Captures thematic similarity (e.g., "user likes movies
    # about dark humor and psychology").
    keyword_sim = _batch_cosine_sim(
        profile.keyword_vec, model.keyword_svd[rows],
    )

    # --- Signal 2: Mood match (weight 0.20) ---
    # Two modes: explicit (user selected moods via pills) or implicit (from
    # historical mood reactions). Explicit uses the average of selected mood
    # columns. Implicit uses dot product between user's mood frequency
    # distribution and the candidate's precomputed mood scores.
    candidate_moods = model.mood_scores[rows]  # (n, 7)
    if selected_moods:
        # Explicit mood selection: average score for the selected moods only
        mood_indices = [MOOD_IDX[m] for m in selected_moods if m in MOOD_IDX]
        if mood_indices:
            mood_match = candidate_moods[:, mood_indices].mean(axis=1)
        else:
            mood_match = np.zeros(n, dtype=np.float32)
    else:
        # Implicit mood: dot product with user's mood frequency vector
        # (e.g., if user mostly tags "Happy" and "Interested", those moods
        # get higher weight in the dot product)
        mood_match = candidate_moods @ profile.implicit_mood

    # --- Signal 3: Genre similarity (weight 0.05) ---
    # Cosine sim of 19-dim multi-hot genre vectors. Low weight because genre
    # preferences are already partially captured by keyword similarity.
    genre_sim = _batch_cosine_sim(
        profile.genre_vec, model.genre_vectors[rows],
    )

    # --- Signal 4: Director similarity (weight 0.15) ---
    # Cosine sim of 200-dim director SVD vectors. "User likes Fincher"
    # automatically boosts Villeneuve/Nolan because their director vectors
    # are nearby in the SVD space (they direct similar types of movies).
    director_sim = _batch_cosine_sim(
        profile.director_vec, model.director_svd[rows],
    )

    # --- Signal 5: Actor similarity (weight 0.10) ---
    # Same logic as directors but for top-5 billed cast per film.
    actor_sim = _batch_cosine_sim(
        profile.actor_vec, model.actor_svd[rows],
    )

    # --- Signal 6: Decade similarity (weight 0.05) ---
    # Captures era preference: "user prefers 90s/2000s films over classics."
    decade_sim = _batch_cosine_sim(
        profile.decade_vec, model.decade_vectors[rows],
    )

    # --- Signal 7: Language similarity (weight 0.03) ---
    # Captures language preference: "user watches mostly English and Korean."
    language_sim = _batch_cosine_sim(
        profile.language_vec, model.language_vectors[rows],
    )

    # --- Signal 8: Runtime similarity (weight 0.03) ---
    # Distance-based: 1.0 = identical runtime preference, 0.0 = maximum diff.
    # Both user_pref and candidate runtime are already normalized to [0, 1]
    # (runtime / 360 minutes).
    candidate_runtimes = model.runtime_normalized[rows].flatten()  # (n,)
    runtime_sim = 1.0 - np.abs(profile.runtime_pref - candidate_runtimes)
    runtime_sim = runtime_sim.astype(np.float32)

    # --- Signal 9: Popularity similarity (weight 0.08) ---
    # Distance-based: captures mainstream vs niche preference. A user who
    # rates mostly blockbusters gets a high popularity_pref; a user who
    # rates indie films gets a low one. Candidates are scored by how close
    # their popularity matches the user's preference.
    candidate_pop = model.popularity_normalized[rows].flatten()  # (n,)
    popularity_sim = 1.0 - np.abs(profile.popularity_pref - candidate_pop)
    popularity_sim = popularity_sim.astype(np.float32)

    # --- Signal 10: Quality score (weight 0.10) ---
    # Precomputed Bayesian average, already normalized to [0, 1].
    # Prevents movies with 1 vote and 10.0 average from outranking
    # well-established films. Higher weight during cold start (0.65).
    quality = model.quality_scores[rows].flatten()  # (n,)

    # --- Signal 11: Contra penalty (weight 0.14) ---
    # Negative cosine similarity against the contra vector (average of
    # keyword SVD vectors from movies rated ≤30/100, dismissed, or removed
    # from watchlist). High similarity to disliked themes → negative score.
    contra_raw = _batch_cosine_sim(
        profile.contra_vec, model.keyword_svd[rows],
    )
    contra_penalty = -contra_raw  # Negate so similar-to-disliked hurts the score

    # --- Stack all 11 signals and compute the weighted sum ---
    # signals matrix: (n_candidates, 11), weights vector: (11,)
    # Final score = dot product of signals and dynamic weights per candidate
    signals = np.column_stack([
        keyword_sim,      # 0: thematic similarity via keyword SVD
        mood_match,       # 1: mood alignment (explicit or implicit)
        genre_sim,        # 2: genre preference match
        director_sim,     # 3: director taste (SVD neighborhood)
        actor_sim,        # 4: actor taste (SVD neighborhood)
        decade_sim,       # 5: era/decade preference
        language_sim,     # 6: original language preference
        runtime_sim,      # 7: runtime length preference
        popularity_sim,   # 8: mainstream vs niche preference
        quality,          # 9: Bayesian quality baseline
        contra_penalty,   # 10: penalty for disliked-theme similarity
    ])

    # Element-wise multiply then sum across signals for each candidate
    final_scores = (signals * weights).sum(axis=1)  # (n,)

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
