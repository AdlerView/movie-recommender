"""TMDB API v3 client. Endpoints and caching: see UTILS.md."""
from __future__ import annotations

import requests
import streamlit as st

# TMDB API v3 base URL and image CDN base
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p"


def _get(
    path: str, extra: dict[str, str | int] | None = None, **params: str | int,
) -> dict:
    """GET request to TMDB with auto-injected API key. Use 'extra' for dotted param keys."""
    if extra:
        params.update(extra)
    params["api_key"] = st.secrets["TMDB_API_KEY"]
    response = requests.get(f"{BASE_URL}{path}", params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def poster_url(path: str | None, size: str = "w342") -> str | None:
    if not path:
        return None
    return f"{IMAGE_BASE}/{size}{path}"


@st.cache_data(ttl="1h", show_spinner=False)
def get_genres() -> list[dict]:
    return _get("/genre/movie/list", language="en")["genres"]


@st.cache_data(ttl="1h", show_spinner=False)
def get_genre_map() -> dict[int, str]:
    return {g["id"]: g["name"] for g in get_genres()}



@st.cache_data(ttl="10m", show_spinner=False)
def discover_movies_filtered(
    params: tuple[tuple[str, str], ...],
    page: int = 1,
) -> dict:
    """Discover movies with arbitrary filters. Params as tuple for Streamlit cache hashability."""
    extra = dict(params)
    extra["page"] = page
    extra["language"] = "en-US"
    return _get("/discover/movie", extra=extra)


@st.cache_data(ttl="24h", show_spinner=False)
def get_languages() -> list[dict]:
    return _get("/configuration/languages")


@st.cache_data(ttl="24h", show_spinner=False)
def get_countries() -> list[dict]:
    return _get("/configuration/countries", language="en")


@st.cache_data(ttl="24h", show_spinner=False)
def get_watch_providers_list(region: str = "CH") -> list[dict]:
    data = _get("/watch/providers/movie", watch_region=region, language="en")
    return data.get("results", [])


@st.cache_data(ttl="5m", show_spinner=False)
def search_keywords(query: str) -> list[dict]:
    if not query.strip():
        return []
    return _get("/search/keyword", query=query, page=1).get("results", [])


@st.cache_data(ttl="5m", show_spinner=False)
def search_movies(query: str, page: int = 1) -> list[dict]:
    return _get("/search/movie", query=query, language="en-US", page=page)["results"]


@st.cache_data(ttl="1h", show_spinner=False)
def get_movie_details(movie_id: int) -> dict:
    """Fetch full details via append_to_response (credits, videos, providers, release_dates, reviews)."""
    return _get(
        f"/movie/{movie_id}",
        append_to_response="credits,videos,watch/providers,release_dates,reviews",
        language="en-US",
    )


@st.cache_data(ttl="1h", show_spinner=False)
def get_movie_keywords(movie_id: int) -> list[dict]:
    # Separate from get_movie_details to avoid cache invalidation
    return _get(f"/movie/{movie_id}/keywords")["keywords"]

