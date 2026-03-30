"""Lazy singleton for precomputed model arrays (numpy + JSON). See SCORING.md."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import numpy as np

log = logging.getLogger(__name__)

# Default output directory for pipeline arrays
_DEFAULT_OUTPUT_DIR: Final[Path] = Path("data/models")


# ---------------------------------------------------------------------------
# Lazy singleton: precomputed model arrays
# ---------------------------------------------------------------------------

@dataclass
class _ModelArrays:
    """Lazy singleton for precomputed arrays. File specs: see MODELS.md."""

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
    """Load all arrays from data/models/."""
    index_path = output_dir / "movie_id_index.json"
    if not index_path.exists():
        raise FileNotFoundError(
            f"movie_id_index.json not found in {output_dir}. "
            "Run the pipeline first (src/ml/index.py)."
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
    """Check whether precomputed model arrays exist on disk."""
    return (output_dir / "movie_id_index.json").exists()
