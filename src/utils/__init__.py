"""Shared UI helpers and constants — re-exports from src.utils.ui."""
from __future__ import annotations

from src.utils.ui import (
    DEFAULT_COUNTRY_CODE,
    DEFAULT_COUNTRY_NAME,
    GRID_COLS,
    MOOD_COLORS,
    RATING_COLORS,
    TMDB_PAGE_SIZE,
    fetch_and_cache_details,
    find_best_trailer,
    inject_poster_grid_css,
    rating_color,
    render_discover_detail,
    render_movie_detail_bottom,
    render_person_ranking,
    render_rating_widget,
    render_watchlist_detail,
)

__all__ = [
    "DEFAULT_COUNTRY_CODE",
    "DEFAULT_COUNTRY_NAME",
    "GRID_COLS",
    "MOOD_COLORS",
    "RATING_COLORS",
    "TMDB_PAGE_SIZE",
    "fetch_and_cache_details",
    "find_best_trailer",
    "inject_poster_grid_css",
    "rating_color",
    "render_discover_detail",
    "render_movie_detail_bottom",
    "render_person_ranking",
    "render_rating_widget",
    "render_watchlist_detail",
]
