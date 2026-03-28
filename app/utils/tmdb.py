"""TMDB API client for the movie recommender.

Provides cached helper functions for all 9 TMDB API v3 endpoints used by the
app. Authentication is handled via st.secrets (API key injected lazily per
request to avoid crash when secrets.toml is missing at import time).

Caching strategy (via @st.cache_data):
    - Configuration data (genres, languages, countries, certifications): 24h TTL
    - Discovery/search results: 5-10 min TTL (unbounded key space)
    - Per-movie details and keywords: 1h TTL (votes change slowly)

All functions raise requests.HTTPError or requests.ConnectionError on failure.
Callers are responsible for catching these and showing appropriate error UI.
"""
from __future__ import annotations

import requests
import streamlit as st

# TMDB API v3 base URL and image CDN base
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
    # Inject API key into every request (lazy access avoids crash on import)
    params["api_key"] = st.secrets["TMDB_API_KEY"]
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



@st.cache_data(ttl="10m", show_spinner=False)
def discover_movies_filtered(
    params: tuple[tuple[str, str], ...],
    page: int = 1,
) -> dict:
    """Fetch movies via the TMDB discover endpoint with arbitrary filters.

    Accepts a tuple of (key, value) pairs as parameters to ensure
    hashability for Streamlit caching. All TMDB discover/movie parameters
    are supported (genre, year, runtime, vote score, providers, etc.).

    Args:
        params: Tuple of (key, value) pairs for TMDB API parameters.
        page: Result page (1-500, 20 results per page).

    Returns:
        Full API response dict with "results", "total_results", "total_pages".
    """
    # GET /discover/movie — filtered discovery with all supported parameters
    extra = dict(params)
    extra["page"] = page
    extra["language"] = "en-US"
    return _get("/discover/movie", extra=extra)


@st.cache_data(ttl="24h", show_spinner=False)
def get_languages() -> list[dict]:
    """Fetch available languages from TMDB configuration.

    Returns:
        List of language dicts with "iso_639_1", "english_name", "name".
    """
    # GET /configuration/languages — all TMDB-supported languages
    return _get("/configuration/languages")


@st.cache_data(ttl="24h", show_spinner=False)
def get_countries() -> list[dict]:
    """Fetch available countries from TMDB configuration.

    Returns:
        List of country dicts with "iso_3166_1", "english_name", "native_name".
    """
    # GET /configuration/countries — all TMDB-supported countries
    return _get("/configuration/countries", language="en")


@st.cache_data(ttl="24h", show_spinner=False)
def get_watch_providers_list(region: str = "CH") -> list[dict]:
    """Fetch available streaming providers for a region.

    Args:
        region: ISO 3166-1 country code (default: CH).

    Returns:
        List of provider dicts with "provider_id", "provider_name", "logo_path".
    """
    # GET /watch/providers/movie — available providers per region
    data = _get("/watch/providers/movie", watch_region=region, language="en")
    return data.get("results", [])


@st.cache_data(ttl="5m", show_spinner=False)
def search_keywords(query: str) -> list[dict]:
    """Search for TMDB keywords by text query.

    Used for keyword autocomplete in the Discover filter sidebar.

    Args:
        query: Search text (min 1 character).

    Returns:
        List of keyword dicts with "id" and "name" keys.
    """
    # GET /search/keyword — keyword text search for autocomplete
    if not query or len(query.strip()) < 1:
        return []
    return _get("/search/keyword", query=query, page=1).get("results", [])


@st.cache_data(ttl="5m", show_spinner=False)
def search_movies(query: str, page: int = 1) -> list[dict]:
    """Search for movies by title via TMDB.

    Searches against title, original title, and alternative titles.
    Used on the Rate page for finding movies the user has already seen.

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
    """Fetch full details for a single movie by ID.

    Uses append_to_response to combine credits, videos, and watch providers
    into a single API call. Returns runtime, genres (full objects), directors
    and cast (credits.crew/cast), trailers (videos), and streaming providers
    (watch/providers) alongside standard movie metadata.

    Args:
        movie_id: TMDB movie ID.

    Returns:
        Full movie details dict with nested credits, videos, and
        watch/providers keys.
    """
    # GET /movie/{id}?append_to_response=credits,videos,watch/providers,release_dates,reviews
    # One call replaces separate requests for credits, videos, providers,
    # country-specific release dates, and user reviews
    return _get(
        f"/movie/{movie_id}",
        append_to_response="credits,videos,watch/providers,release_dates,reviews",
        language="en-US",
    )


@st.cache_data(ttl="1h", show_spinner=False)
def get_movie_keywords(movie_id: int) -> list[dict]:
    """Fetch keywords for a movie.

    Keywords are thematic tags assigned by TMDB (e.g., "time travel",
    "dystopia"). Useful for content-based ML filtering and keyword clouds.
    Separate from get_movie_details to avoid cache invalidation.

    Args:
        movie_id: TMDB movie ID.

    Returns:
        List of keyword dicts with "id" and "name" keys.
    """
    # GET /movie/{id}/keywords — thematic tags for content analysis
    return _get(f"/movie/{movie_id}/keywords")["keywords"]

