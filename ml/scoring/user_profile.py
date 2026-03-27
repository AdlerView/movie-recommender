"""User profile computation from ratings and precomputed feature arrays.

Builds a personalized user profile by computing weighted averages of movie
feature vectors based on the user's rating history. The profile captures
preferences across 8 dimensions: keywords, directors, actors, decades,
languages, runtime, mood, and contra (disliked themes).

The precomputed .npy arrays (~3 GB total, 1.17M movies) are loaded once
via a lazy singleton and shared across all Streamlit sessions (same process).

Profile vectors are recomputed after each new rating and cached in the
user_profile_cache SQLite table to avoid recomputation on page reload.

Weight formula (SCORING.md):
    weight = (rating - 50) / 50
    → rating 100 = +1.0 (strong positive signal)
    → rating  50 =  0.0 (neutral, no influence)
    → rating   0 = -1.0 (strong negative signal)

Data flow:
    data/output/*.npy + movie_id_index.json  (read-only, loaded once)
    data/user.sqlite user_ratings            (read per recomputation)
    data/user.sqlite user_rating_moods       (read per recomputation)
    data/user.sqlite dismissed               (read per recomputation)
        → UserProfile dataclass with 8 numpy vectors
        → cached in user_profile_cache (key-value BLOB store)
"""
from __future__ import annotations

import hashlib
import json
import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import numpy as np

from app.utils.db import load_dismissed, load_mood_reactions, load_ratings

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
    """Container for all precomputed .npy arrays and the movie ID index.

    Loaded once on first access, then cached at module level. All arrays
    share the same row ordering (SELECT id FROM movies ORDER BY id).
    """

    movie_id_index: dict[str, int] = field(default_factory=dict)
    keyword_svd: np.ndarray = field(default_factory=lambda: np.empty(0))
    director_svd: np.ndarray = field(default_factory=lambda: np.empty(0))
    actor_svd: np.ndarray = field(default_factory=lambda: np.empty(0))
    genre_vectors: np.ndarray = field(default_factory=lambda: np.empty(0))
    decade_vectors: np.ndarray = field(default_factory=lambda: np.empty(0))
    language_vectors: np.ndarray = field(default_factory=lambda: np.empty(0))
    runtime_normalized: np.ndarray = field(default_factory=lambda: np.empty(0))
    mood_scores: np.ndarray = field(default_factory=lambda: np.empty(0))
    quality_scores: np.ndarray = field(default_factory=lambda: np.empty(0))


_model: _ModelArrays | None = None


def _load_model_arrays(output_dir: Path = _DEFAULT_OUTPUT_DIR) -> _ModelArrays:
    """Load all precomputed arrays from data/output/.

    Args:
        output_dir: Directory containing .npy files and movie_id_index.json.

    Returns:
        Populated _ModelArrays instance.

    Raises:
        FileNotFoundError: If movie_id_index.json or any required .npy is missing.
    """
    index_path = output_dir / "movie_id_index.json"
    if not index_path.exists():
        raise FileNotFoundError(
            f"movie_id_index.json not found in {output_dir}. "
            "Run the pipeline first (ml/extraction/04_build_index.py)."
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
        mood_scores=np.load(output_dir / "mood_scores.npy"),
        quality_scores=np.load(output_dir / "quality_scores.npy"),
    )


def get_model() -> _ModelArrays:
    """Return the lazily-loaded model arrays singleton.

    First call loads ~3 GB of .npy files into memory. Subsequent calls
    return the cached instance. Thread-safe in CPython due to the GIL.

    Returns:
        The shared _ModelArrays instance.
    """
    global _model  # noqa: PLW0603
    if _model is None:
        _model = _load_model_arrays()
    return _model


def is_model_available(output_dir: Path = _DEFAULT_OUTPUT_DIR) -> bool:
    """Check whether the pipeline output files exist.

    Args:
        output_dir: Directory to check for movie_id_index.json.

    Returns:
        True if the model files are present and can be loaded.
    """
    return (output_dir / "movie_id_index.json").exists()


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------


def _compute_fingerprint(
    ratings: dict[int, int],
    mood_reactions: dict[int, list[str]],
    dismissed: set[int],
) -> str:
    """Compute a hash fingerprint of the input data for cache invalidation.

    Changes to any rating value, mood reaction, or dismissed movie will
    produce a different fingerprint, triggering profile recomputation.

    Args:
        ratings: movie_id → rating dict.
        mood_reactions: movie_id → mood list dict.
        dismissed: set of dismissed movie IDs.

    Returns:
        Hex digest string (MD5, 32 chars).
    """
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
    """Personalized user profile computed from rating history.

    Each vector captures the user's preference in one feature dimension.
    Used by the scoring module to compute cosine similarity against
    candidate movie vectors.

    Attributes:
        keyword_vec: Weighted average of keyword SVD vectors (200-dim).
        genre_vec: Weighted average of genre multi-hot vectors (19-dim).
        director_vec: Weighted average of director SVD vectors (200-dim).
        actor_vec: Weighted average of actor SVD vectors (200-dim).
        decade_vec: Weighted average of decade onehot vectors (15-dim).
        language_vec: Weighted average of language onehot vectors (20-dim).
        runtime_pref: Weighted average runtime from positively-rated movies (scalar).
        implicit_mood: Normalized frequency of mood tags from reactions (7-dim).
        contra_vec: Average keyword SVD vector from disliked/dismissed movies (200-dim).
        rating_count: Number of rated movies (determines dynamic weight tier).
        fingerprint: Hash of input data (ratings + moods + dismissed) for cache invalidation.
    """

    keyword_vec: np.ndarray
    genre_vec: np.ndarray
    director_vec: np.ndarray
    actor_vec: np.ndarray
    decade_vec: np.ndarray
    language_vec: np.ndarray
    runtime_pref: float
    implicit_mood: np.ndarray
    contra_vec: np.ndarray
    rating_count: int
    fingerprint: str = ""


def _movie_id_to_row(movie_id: int, index: dict[str, int]) -> int | None:
    """Look up the row index for a movie ID.

    Args:
        movie_id: TMDB movie ID.
        index: movie_id_index mapping (string keys → int row indices).

    Returns:
        Row index, or None if the movie is not in the precomputed arrays.
    """
    return index.get(str(movie_id))


def _weighted_average(
    vectors: np.ndarray,
    row_indices: list[int],
    weights: list[float],
) -> np.ndarray:
    """Compute a weighted average of selected rows from a feature matrix.

    Args:
        vectors: Feature matrix of shape (n_movies, dim).
        row_indices: Row indices to select.
        weights: Weight per row (same length as row_indices).

    Returns:
        Weighted average vector of shape (dim,). Returns zero vector if
        all weights are zero or no valid rows exist.
    """
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
    """Compute a full user profile from rating history.

    Loads ratings and mood reactions from the database if not provided.
    Looks up precomputed feature vectors for each rated movie and computes
    weighted averages across all dimensions.

    Args:
        ratings: Optional pre-loaded ratings dict (movie_id → 0-100).
            Loaded from DB if None.
        mood_reactions: Optional pre-loaded mood reactions dict
            (movie_id → list of mood strings). Loaded from DB if None.
        dismissed: Optional pre-loaded dismissed set. Loaded from DB if None.

    Returns:
        UserProfile with all 8 preference vectors computed.
    """
    # Load data from DB if not provided
    if ratings is None:
        ratings = load_ratings()
    if mood_reactions is None:
        mood_reactions = load_mood_reactions()
    if dismissed is None:
        dismissed = load_dismissed()

    model = get_model()
    index = model.movie_id_index

    # --- Resolve movie IDs to row indices and compute weights ---
    # Weight formula: (rating - 50) / 50 → maps [0, 100] to [-1.0, +1.0]
    row_indices: list[int] = []
    weights: list[float] = []
    positive_row_indices: list[int] = []
    positive_weights: list[float] = []
    contra_row_indices: list[int] = []

    for movie_id, rating in ratings.items():
        row = _movie_id_to_row(movie_id, index)
        if row is None:
            continue  # Movie not in precomputed arrays (e.g., very new movie)

        w = (rating - 50) / 50.0
        row_indices.append(row)
        weights.append(w)

        # Positive ratings (> 50) for runtime preference
        if rating > POSITIVE_THRESHOLD:
            positive_row_indices.append(row)
            positive_weights.append(w)

        # Low ratings (0-30) for contra vector
        if rating <= CONTRA_THRESHOLD:
            contra_row_indices.append(row)

    # Dismissed movies also contribute to the contra vector
    for movie_id in dismissed:
        row = _movie_id_to_row(movie_id, index)
        if row is not None:
            contra_row_indices.append(row)

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
        implicit_mood=implicit_mood,
        contra_vec=contra_vec,
        rating_count=len(ratings),
        fingerprint=_compute_fingerprint(ratings, mood_reactions, dismissed),
    )


# ---------------------------------------------------------------------------
# SQLite cache (user_profile_cache table)
# ---------------------------------------------------------------------------

def save_profile_to_cache(profile: UserProfile) -> None:
    """Serialize and save the user profile to the SQLite cache.

    Uses pickle to serialize the UserProfile dataclass into a single BLOB
    stored under the key "user_profile" in the user_profile_cache table.

    Args:
        profile: Computed user profile to cache.
    """
    from app.utils.db import save_profile_cache

    blob = pickle.dumps(profile)
    save_profile_cache("user_profile", blob)
    log.info("User profile cached (%d bytes)", len(blob))


def load_profile_from_cache() -> UserProfile | None:
    """Load the cached user profile from SQLite.

    Returns:
        Cached UserProfile, or None if no cache exists.
    """
    from app.utils.db import load_profile_cache

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
    """Get the user profile, using cache when possible.

    Returns the cached profile if the rating count matches the current
    number of ratings. Otherwise recomputes and caches the new profile.

    Returns None if no ratings exist (cold start) or if the model files
    are not available.

    Args:
        ratings: Optional pre-loaded ratings dict. Loaded from DB if None.
        mood_reactions: Optional pre-loaded mood reactions. Loaded from DB if None.
        dismissed: Optional pre-loaded dismissed set. Loaded from DB if None.
        force_recompute: Skip cache and always recompute.

    Returns:
        UserProfile, or None if no ratings or model unavailable.
    """
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
