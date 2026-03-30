"""SQLite cache for serialized user profiles. See SCORING.md."""
from __future__ import annotations

import hashlib
import logging
import pickle

from src.scoring.loader import is_model_available
from src.scoring.profile import UserProfile, compute_user_profile
from src.db import load_dismissed, load_mood_reactions, load_ratings

log = logging.getLogger(__name__)


def compute_fingerprint(
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


def save_profile_to_cache(profile: UserProfile) -> None:
    """Serialize and save profile to SQLite cache."""
    from src.db import save_profile_cache

    blob = pickle.dumps(profile)
    save_profile_cache("user_profile", blob)
    log.info("User profile cached (%d bytes)", len(blob))


def load_profile_from_cache() -> UserProfile | None:
    """Load cached profile, or None if missing/corrupt."""
    from src.db import load_profile_cache

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
    current_fp = compute_fingerprint(ratings, mood_reactions, dismissed)
    if not force_recompute:
        cached = load_profile_from_cache()
        if cached is not None and cached.fingerprint == current_fp:
            return cached

    # Recompute
    profile = compute_user_profile(ratings, mood_reactions, dismissed)
    save_profile_to_cache(profile)
    return profile
