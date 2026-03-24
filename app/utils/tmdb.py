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


def _get(
    path: str, extra: dict[str, str | int] | None = None, **params: str | int,
) -> dict:
    """Send a GET request to the TMDB API.

    Injects the API key automatically and raises on HTTP errors.

    Args:
        path: API endpoint path (e.g., "/genre/movie/list").
        extra: Additional query parameters with keys that are not valid Python
            identifiers (e.g., "vote_count.gte").
        **params: Query parameters forwarded to the request.

    Returns:
        Parsed JSON response as a dictionary.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status code.
        requests.ConnectionError: If the connection to TMDB fails.
    """
    # Merge extra params (for dotted keys like "vote_count.gte") into kwargs
    if extra:
        params.update(extra)
    # Inject API key into every request automatically
    params["api_key"] = API_KEY
    response = requests.get(f"{BASE_URL}{path}", params=params, timeout=10)
    response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses
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
def get_trending(time_window: str = "week", page: int = 1) -> list[dict]:
    """Fetch trending movies from TMDB.

    Args:
        time_window: "day" or "week".
        page: Result page (1-500, 20 movies per page).

    Returns:
        List of movie dicts from the trending endpoint.
    """
    # GET /trending/movie/{time_window} — movies trending this day/week
    return _get(f"/trending/movie/{time_window}", language="en-US", page=page)["results"]


@st.cache_data(ttl="30m", show_spinner="Discovering movies...")
def discover_movies(genre_ids: tuple[int, ...], page: int = 1) -> list[dict]:
    """Fetch movies filtered by genres via the TMDB discover endpoint.

    Uses AND logic for genres so movies must match all selected genres.
    Results are sorted by rating with a minimum vote count to filter obscure films.

    Args:
        genre_ids: TMDB genre IDs to filter by (AND logic).
        page: Result page (1-500).

    Returns:
        List of movie dicts matching all selected genres.
    """
    # GET /discover/movie — genre-filtered discovery, AND logic via comma separator
    # Sorted by popularity (composite of votes, views, watchlist adds, trending)
    genres_param = ",".join(str(gid) for gid in genre_ids)
    return _get(
        "/discover/movie",
        extra={"vote_count.gte": 100},
        with_genres=genres_param,
        sort_by="popularity.desc",
        language="en-US",
        page=page,
    )["results"]


@st.cache_data(ttl="5m", show_spinner=False)
def search_movies(query: str, page: int = 1) -> list[dict]:
    """Search for movies by title via TMDB.

    Searches against title, original title, and alternative titles.
    Used on the Watched page for finding movies the user has already seen.

    Args:
        query: Search text (min 1 character).
        page: Result page (1-500, 20 movies per page).

    Returns:
        List of movie dicts matching the search query.
    """
    # GET /search/movie — text-based title search
    return _get("/search/movie", query=query, language="en-US", page=page)["results"]


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


@st.cache_data(ttl="1h", show_spinner=False)
def get_watch_providers(movie_id: int, region: str = "CH") -> list[dict]:
    """Fetch flatrate streaming providers for a movie in a given region.

    Args:
        movie_id: TMDB movie ID.
        region: ISO 3166-1 country code (default: CH for Switzerland).

    Returns:
        List of provider dicts with "provider_name" and "logo_path" keys.
        Empty list if no flatrate providers are available in the region.
    """
    # GET /movie/{id}/watch/providers — streaming availability per country
    data = _get(f"/movie/{movie_id}/watch/providers")
    # Response is keyed by ISO 3166-1 country code (e.g., "CH", "DE", "US")
    country = data.get("results", {}).get(region, {})
    # Return only flatrate (subscription) providers; ignore rent/buy/ads
    return country.get("flatrate", [])
