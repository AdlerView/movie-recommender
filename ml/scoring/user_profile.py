"""User profile from ratings: weighted-average feature vectors. See SCORING.md."""
from __future__ import annotations

import hashlib
import json
import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import numpy as np

from src.utils.db import load_dismissed, load_mood_reactions, load_ratings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# 7 canonical mood categories in fixed order (must match mood_scores.npy columns)
MOODS: Final[list[str]] = [
    "Happy", "Interested", "Surprised", "Sad", "Disgusted", "Afraid", "Angry",
]
MOOD_IDX: Final[dict[str, int]] = {m: i for i, m in enumerate(MOODS)}

# Rating thresholds (from SCORING.md)
CONTRA_THRESHOLD: Final[int] = 30  # ratings 0-30 contribute to contra vector
POSITIVE_THRESHOLD: Final[int] = 50  # ratings > 50 used for runtime preference

# Default output directory for pipeline arrays
_DEFAULT_OUTPUT_DIR: Final[Path] = Path("data/output")


# ---------------------------------------------------------------------------
# Lazy singleton: precomputed model arrays
# ---------------------------------------------------------------------------

@dataclass
class _ModelArrays:
    """Lazy singleton for precomputed arrays. File specs: see OUTPUT.md."""

    movie_id_index: dict[str, int] = field(default_factory=dict)
    keyword_svd: np.ndarray = field(default_factory=lambda: np.empty(0))
    director_svd: np.ndarray = field(default_factory=lambda: np.empty(0))
    actor_svd: np.ndarray = field(default_factory=lambda: np.empty(0))
    genre_vectors: np.ndarray = field(default_factory=lambda: np.empty(0))
    decade_vectors: np.ndarray = field(default_factory=lambda: np.empty(0))
    language_vectors: np.ndarray = field(default_factory=lambda: np.empty(0))
    runtime_normalized: np.ndarray = field(default_factory=lambda: np.empty(0))
    popularity_normalized: np.ndarray = field(default_factory=lambda: np.empty(0))
    mood_scores: np.ndarray = field(default_factory=lambda: np.empty(0))
    quality_scores: np.ndarray = field(default_factory=lambda: np.empty(0))


_model: _ModelArrays | None = None


def _load_model_arrays(output_dir: Path = _DEFAULT_OUTPUT_DIR) -> _ModelArrays:
    """Load all arrays from data/output/."""
    index_path = output_dir / "movie_id_index.json"
    if not index_path.exists():
        raise FileNotFoundError(
            f"movie_id_index.json not found in {output_dir}. "
            "Run the pipeline first (ml/extraction/build_index.py)."
        )

    with open(index_path) as f:
        movie_id_index = json.load(f)

    log.info("Loading model arrays from %s (%d movies)", output_dir, len(movie_id_index))

    return _ModelArrays(
        movie_id_index=movie_id_index,
        keyword_svd=np.load(output_dir / "keyword_svd_vectors.npy"),
        director_svd=np.load(output_dir / "director_svd_vectors.npy"),
        actor_svd=np.load(output_dir / "actor_svd_vectors.npy"),
        genre_vectors=np.load(output_dir / "genre_vectors.npy"),
        decade_vectors=np.load(output_dir / "decade_vectors.npy"),
        language_vectors=np.load(output_dir / "language_vectors.npy"),
        runtime_normalized=np.load(output_dir / "runtime_normalized.npy"),
        popularity_normalized=np.load(output_dir / "popularity_normalized.npy"),
        mood_scores=np.load(output_dir / "mood_scores.npy"),
        quality_scores=np.load(output_dir / "quality_scores.npy"),
    )


def get_model() -> _ModelArrays:
    """Return lazily-loaded model arrays singleton."""
    global _model  # noqa: PLW0603
    if _model is None:
        _model = _load_model_arrays()
    return _model


def is_model_available(output_dir: Path = _DEFAULT_OUTPUT_DIR) -> bool:
    return (output_dir / "movie_id_index.json").exists()


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------


def _compute_fingerprint(
    ratings: dict[int, int],
    mood_reactions: dict[int, list[str]],
    dismissed: set[int],
) -> str:
    """MD5 hash of ratings + moods + dismissed for cache invalidation."""
    h = hashlib.md5(usedforsecurity=False)
    # Sorted ratings: captures both count and values
    for mid, rating in sorted(ratings.items()):
        h.update(f"{mid}:{rating}".encode())
    # Sorted mood reactions
    for mid, moods in sorted(mood_reactions.items()):
        h.update(f"{mid}:{','.join(sorted(moods))}".encode())
    # Sorted dismissed
    for mid in sorted(dismissed):
        h.update(f"d:{mid}".encode())
    return h.hexdigest()


@dataclass
class UserProfile:
    """User preference vectors for cosine similarity scoring. See SCORING.md."""

    keyword_vec: np.ndarray
    genre_vec: np.ndarray
    director_vec: np.ndarray
    actor_vec: np.ndarray
    decade_vec: np.ndarray
    language_vec: np.ndarray
    runtime_pref: float
    popularity_pref: float
    implicit_mood: np.ndarray
    contra_vec: np.ndarray
    rating_count: int
    fingerprint: str = ""


def _movie_id_to_row(movie_id: int, index: dict[str, int]) -> int | None:
    return index.get(str(movie_id))


def _weighted_average(
    vectors: np.ndarray,
    row_indices: list[int],
    weights: list[float],
) -> np.ndarray:
    """Weighted average of selected rows. Zero vector if no valid rows."""
    if not row_indices:
        return np.zeros(vectors.shape[1], dtype=np.float32)

    selected = vectors[row_indices]  # (n, dim)
    w = np.array(weights, dtype=np.float32)  # (n,)

    # Avoid division by zero when all weights cancel out
    w_sum = np.abs(w).sum()
    if w_sum < 1e-9:
        return np.zeros(vectors.shape[1], dtype=np.float32)

    return (selected * w[:, np.newaxis]).sum(axis=0) / w_sum


def compute_user_profile(
    ratings: dict[int, int] | None = None,
    mood_reactions: dict[int, list[str]] | None = None,
    dismissed: set[int] | None = None,
) -> UserProfile:
    """Compute user profile from ratings, moods, dismissed. See SCORING.md."""
    # Load data from DB if not provided
    if ratings is None:
        ratings = load_ratings()
    if mood_reactions is None:
        mood_reactions = load_mood_reactions()
    if dismissed is None:
        dismissed = load_dismissed()

    model = get_model()
    index = model.movie_id_index

    # Weight: (rating - 50) / 50 — see SCORING.md
    row_indices: list[int] = []     # All rated movies (for preference vectors)
    weights: list[float] = []       # Corresponding centered weights
    positive_row_indices: list[int] = []  # Only liked movies (for runtime pref)
    positive_weights: list[float] = []
    contra_row_indices: list[int] = []    # Disliked + dismissed (for contra vec)

    for movie_id, rating in ratings.items():
        row = _movie_id_to_row(movie_id, index)
        if row is None:
            continue  # Movie not in precomputed arrays (e.g., very new movie)

        # Center the rating: 50 → 0.0, 100 → +1.0, 0 → -1.0
        w = (rating - 50) / 50.0
        row_indices.append(row)
        weights.append(w)

        # Positive ratings (> 50) contribute to runtime preference.
        # Runtime pref uses only liked movies to compute average preferred length.
        if rating > POSITIVE_THRESHOLD:
            positive_row_indices.append(row)
            positive_weights.append(w)

        # Low ratings (0-30) indicate dislike — these movies contribute to the
        # contra vector, which penalizes thematically similar candidates.
        if rating <= CONTRA_THRESHOLD:
            contra_row_indices.append(row)

    # Dismissed movies ("not interested" on Discover, or removed from watchlist)
    # are treated as negative signal in the contra vector, same as ratings ≤ 30.
    for movie_id in dismissed:
        row = _movie_id_to_row(movie_id, index)
        if row is not None:
            contra_row_indices.append(row)

    # Watchlisted movies as weak positive signal — see SCORING.md
    from src.utils.db import load_watchlist
    _watchlist = load_watchlist()
    _watchlist_weight = 0.3
    for movie in _watchlist:
        row = _movie_id_to_row(movie["id"], index)
        if row is not None and movie["id"] not in ratings:
            row_indices.append(row)
            weights.append(_watchlist_weight)

    # --- Compute weighted-average profile vectors ---
    keyword_vec = _weighted_average(model.keyword_svd, row_indices, weights)
    genre_vec = _weighted_average(model.genre_vectors, row_indices, weights)
    director_vec = _weighted_average(model.director_svd, row_indices, weights)
    actor_vec = _weighted_average(model.actor_svd, row_indices, weights)
    decade_vec = _weighted_average(model.decade_vectors, row_indices, weights)
    language_vec = _weighted_average(model.language_vectors, row_indices, weights)

    # Runtime preference: weighted average from positively-rated movies only
    if positive_row_indices:
        runtime_pref = float(_weighted_average(
            model.runtime_normalized, positive_row_indices, positive_weights,
        )[0])
    else:
        runtime_pref = 0.0

    # Popularity preference: mainstream vs niche — see SCORING.md
    if positive_row_indices:
        popularity_pref = float(_weighted_average(
            model.popularity_normalized, positive_row_indices, positive_weights,
        )[0])
    else:
        popularity_pref = 0.0

    # Contra vector: simple average of keyword SVD vectors from disliked/dismissed
    if contra_row_indices:
        contra_vec = model.keyword_svd[contra_row_indices].mean(axis=0)
    else:
        contra_vec = np.zeros(model.keyword_svd.shape[1], dtype=np.float32)

    # --- Implicit mood: normalized frequency of mood tags ---
    implicit_mood = np.zeros(len(MOODS), dtype=np.float32)
    total_tags = 0
    for moods in mood_reactions.values():
        for mood in moods:
            if mood in MOOD_IDX:
                implicit_mood[MOOD_IDX[mood]] += 1.0
                total_tags += 1

    # Normalize to unit sum (frequency distribution)
    if total_tags > 0:
        implicit_mood /= total_tags

    log.info(
        "User profile computed: %d ratings, %d positive, %d contra, %d mood tags",
        len(row_indices), len(positive_row_indices),
        len(contra_row_indices), total_tags,
    )

    return UserProfile(
        keyword_vec=keyword_vec,
        genre_vec=genre_vec,
        director_vec=director_vec,
        actor_vec=actor_vec,
        decade_vec=decade_vec,
        language_vec=language_vec,
        runtime_pref=runtime_pref,
        popularity_pref=popularity_pref,
        implicit_mood=implicit_mood,
        contra_vec=contra_vec,
        rating_count=len(ratings),
        fingerprint=_compute_fingerprint(ratings, mood_reactions, dismissed),
    )


# ---------------------------------------------------------------------------
# SQLite cache (user_profile_cache table)
# ---------------------------------------------------------------------------

def save_profile_to_cache(profile: UserProfile) -> None:
    """Serialize and save profile to SQLite cache."""
    from src.utils.db import save_profile_cache

    blob = pickle.dumps(profile)
    save_profile_cache("user_profile", blob)
    log.info("User profile cached (%d bytes)", len(blob))


def load_profile_from_cache() -> UserProfile | None:
    """Load cached profile, or None if missing/corrupt."""
    from src.utils.db import load_profile_cache

    blob = load_profile_cache("user_profile")
    if blob is None:
        return None

    try:
        profile = pickle.loads(blob)
        if isinstance(profile, UserProfile):
            log.info("User profile loaded from cache (%d ratings)", profile.rating_count)
            return profile
    except (pickle.UnpicklingError, AttributeError, TypeError):
        log.warning("Corrupt profile cache, will recompute")

    return None


def get_or_compute_profile(
    ratings: dict[int, int] | None = None,
    mood_reactions: dict[int, list[str]] | None = None,
    dismissed: set[int] | None = None,
    force_recompute: bool = False,
) -> UserProfile | None:
    """Get profile from cache or recompute if fingerprint changed. None on cold start."""
    if not is_model_available():
        return None

    if ratings is None:
        ratings = load_ratings()
    if mood_reactions is None:
        mood_reactions = load_mood_reactions()
    if dismissed is None:
        dismissed = load_dismissed()

    if not ratings:
        return None

    # Check cache validity via fingerprint (captures rating values, moods, dismissals)
    current_fp = _compute_fingerprint(ratings, mood_reactions, dismissed)
    if not force_recompute:
        cached = load_profile_from_cache()
        if cached is not None and cached.fingerprint == current_fp:
            return cached

    # Recompute
    profile = compute_user_profile(ratings, mood_reactions, dismissed)
    save_profile_to_cache(profile)
    return profile
