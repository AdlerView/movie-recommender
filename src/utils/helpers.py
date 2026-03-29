"""Data helpers (no Streamlit). Pure functions and data-layer logic."""
from __future__ import annotations

import sqlite3
from datetime import datetime

import requests

from src.utils.constants import (
    DEFAULT_COUNTRY_CODE,
    DEFAULT_COUNTRY_NAME,
    RATING_COLORS,
)
from src.utils.db import load_preference
from src.utils.tmdb import get_countries, get_movie_keywords, poster_url  # noqa: F401 (re-used by ui.py)


def rating_color(value: int | float, scale: int = 100) -> str:
    """Return hex color for a rating value (5-level scale, normalized via scale param)."""
    normalized = (value / scale) * 100 if scale != 100 else value
    for threshold, color in RATING_COLORS:
        if normalized <= threshold:
            return color
    return RATING_COLORS[-1][1]


def find_best_trailer(details: dict) -> dict | None:
    """Find best YouTube trailer (official first, newest first)."""
    videos = details.get("videos", {}).get("results", [])
    trailers = [
        v for v in videos
        if v.get("site") == "YouTube" and v.get("type") == "Trailer"
    ]
    if not trailers:
        return None
    trailers.sort(
        key=lambda v: (v.get("official", False), v.get("published_at", "")),
        reverse=True,
    )
    return trailers[0]


def format_release_date(details: dict, country_code: str) -> str | None:
    """Format release date: country-specific type 3 (theatrical) → type 4 (digital) → global fallback."""
    release_dates_data = details.get("release_dates", {}).get("results", [])
    for country_entry in release_dates_data:
        if country_entry.get("iso_3166_1") == country_code:
            dates = country_entry.get("release_dates", [])
            # Prefer theatrical (type 3), then digital (4), then any
            for preferred_type in (3, 4):
                for rd in dates:
                    if rd.get("type") == preferred_type and rd.get("release_date"):
                        try:
                            dt = datetime.fromisoformat(
                                rd["release_date"].replace("Z", "+00:00"),
                            )
                            return dt.strftime("%B %-d, %Y")
                        except ValueError:
                            continue
            # Fallback: first available date for this country
            if dates and dates[0].get("release_date"):
                try:
                    dt = datetime.fromisoformat(
                        dates[0]["release_date"].replace("Z", "+00:00"),
                    )
                    return dt.strftime("%B %-d, %Y")
                except ValueError:
                    pass
            break
    # Global fallback: release_date from movie details
    global_date = details.get("release_date")
    if global_date:
        try:
            dt = datetime.strptime(global_date, "%Y-%m-%d")
            return dt.strftime("%B %-d, %Y")
        except ValueError:
            return global_date
    return None


def resolve_country_code() -> str:
    """Resolve streaming country preference to ISO 3166-1 code."""
    pref_name = load_preference("streaming_country", DEFAULT_COUNTRY_NAME)
    try:
        countries = get_countries()
        code = next(
            (c["iso_3166_1"] for c in countries
             if c.get("english_name") == pref_name),
            DEFAULT_COUNTRY_CODE,
        )
    except requests.RequestException:
        code = DEFAULT_COUNTRY_CODE
    return code


def fetch_and_cache_details(movie_id: int, details: dict) -> None:
    """Fetch keywords and cache details + keywords to SQLite (best-effort)."""
    from src.utils.db import save_movie_details

    try:
        keywords = get_movie_keywords(movie_id)
    except requests.RequestException:
        keywords = None
    try:
        save_movie_details(movie_id, details, keywords=keywords)
    except sqlite3.Error:
        pass
