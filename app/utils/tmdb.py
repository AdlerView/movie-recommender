"""TMDB API client for the movie recommender.

Provides cached helper functions for TMDB API v3 endpoints used by the app.
Authentication is handled via st.secrets. All public functions cache responses
with appropriate TTLs to minimize API calls.
"""
from __future__ import annotations

import requests
import streamlit as st

# TMDB API v3 base URL and image CDN base
API_KEY: str = st.secrets["TMDB_API_KEY"]
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p"


def _get(path: str, **params: str | int) -> dict:
    """Send a GET request to the TMDB API.

    Injects the API key automatically and raises on HTTP errors.

    Args:
        path: API endpoint path (e.g., "/genre/movie/list").
        **params: Query parameters forwarded to the request.

    Returns:
        Parsed JSON response as a dictionary.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
        requests.ConnectionError: If the connection to TMDB fails.
    """
    params["api_key"] = API_KEY
    response = requests.get(f"{BASE_URL}{path}", params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def poster_url(path: str | None, size: str = "w342") -> str | None:
    """Build a full TMDB poster image URL.

    Args:
        path: Relative poster path from TMDB (e.g., "/abc123.jpg").
        size: Image size preset. Use "w342" for cards, "w500" for details.

    Returns:
        Full image URL, or None if path is missing.
    """
    if not path:
        return None
    return f"{IMAGE_BASE}/{size}{path}"


@st.cache_data(ttl="1h", show_spinner=False)
def get_genres() -> list[dict]:
    """Fetch the list of movie genres from TMDB.

    Cached for 1 hour since genres rarely change.

    Returns:
        List of genre dicts with "id" and "name" keys.
    """
    # GET /genre/movie/list — returns all available movie genres
    return _get("/genre/movie/list", language="en")["genres"]


@st.cache_data(ttl="1h", show_spinner=False)
def get_genre_map() -> dict[int, str]:
    """Build a mapping from genre ID to genre name.

    Useful for resolving genre_ids in movie results to display names.

    Returns:
        Dict mapping genre ID (int) to genre name (str).
    """
    return {g["id"]: g["name"] for g in get_genres()}


@st.cache_data(ttl="30m", show_spinner="Loading trending movies...")
def get_trending(time_window: str = "week") -> list[dict]:
    """Fetch trending movies from TMDB.

    Args:
        time_window: "day" or "week".

    Returns:
        List of movie dicts from the trending endpoint.
    """
    # GET /trending/movie/{time_window} — movies trending this day/week
    return _get(f"/trending/movie/{time_window}", language="en-US")["results"]


@st.cache_data(ttl="1h", show_spinner=False)
def get_movie_details(movie_id: int) -> dict:
    """Fetch details for a single movie by ID.

    Used to retrieve metadata (title, poster, rating) for movies that were
    rated but not added to the watchlist.

    Args:
        movie_id: TMDB movie ID.

    Returns:
        Full movie details dict from TMDB.
    """
    # GET /movie/{id} — full movie details
    return _get(f"/movie/{movie_id}", language="en-US")
