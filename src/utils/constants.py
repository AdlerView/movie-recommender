"""App-wide constants. No dependencies."""
from __future__ import annotations

from typing import Final

# Layout
GRID_COLS: Final[int] = 5
TMDB_PAGE_SIZE: Final[int] = 20

# Default streaming country
DEFAULT_COUNTRY_NAME: Final[str] = "Switzerland"
DEFAULT_COUNTRY_CODE: Final[str] = "CH"

# 5-level rating color scale (0-100)
RATING_COLORS: Final[list[tuple[int, str]]] = [
    (20, "#ff4b4b"),   # 0-20: Awful (red)
    (40, "#ffa421"),   # 21-40: Poor (orange)
    (60, "#e8c840"),   # 41-60: Decent (yellow)
    (80, "#85cc5a"),   # 61-80: Great (light green)
    (100, "#21c354"),  # 81-100: Masterpiece (green)
]

# Mood colors (Ekman model)
MOOD_COLORS: Final[dict[str, str]] = {
    "Happy": "#FFD700",
    "Interested": "#1c83e1",
    "Surprised": "#ffa421",
    "Sad": "#6c8ebf",
    "Disgusted": "#803df5",
    "Afraid": "#ff4b4b",
    "Angry": "#cc0000",
}

# Genre pill order optimized for sidebar width
GENRE_ORDER: Final[list[str]] = [
    "War", "Music", "Crime",
    "Drama", "Horror", "Family",
    "Action", "Comedy", "History",
    "Western", "Mystery", "Fantasy",
    "Romance", "Thriller", "Adventure",
    "Animation", "TV Movie", "Documentary",
    "Science Fiction",
]

# Default discover params for the Rate browse grid
RATE_DISCOVER_PARAMS: Final[tuple[tuple[str, str], ...]] = (
    ("sort_by", "popularity.desc"),
    ("vote_count.gte", "50"),
)
