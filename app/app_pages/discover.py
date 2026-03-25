"""Discover page — Browse and discover new movies by genre.

Two-phase flow: first select genre tags, then browse filtered movies one at a
time in a card-based flow. Genres are hard AND filters via TMDB API. Add to
watchlist or dismiss. Rating happens on the Rate page.
"""
from __future__ import annotations

import requests
import streamlit as st
from utils.db import (
    save_dismissed,
    save_to_watchlist,
)
from utils.tmdb import (
    discover_movies,
    get_genre_map,
    get_movie_details,
    get_trending,
    poster_url,
)

# Provider brand colors for streaming badges (same mapping as Watchlist page)
_PROVIDER_COLORS: dict[str, str] = {
    "Netflix": "red",
    "Amazon Prime Video": "blue",
    "Disney Plus": "green",
    "Apple TV Plus": "gray",
    "Paramount Plus": "orange",
}
_DEFAULT_PROVIDER_COLOR = "violet"

# Header changes based on phase: genre selection vs. movie browsing
if st.session_state.get("discover_phase", "select") == "select":
    st.header("Which movie will you watch?", divider="gray", text_alignment="center")
else:
    st.header("Discover movies", divider="gray")

# --- Deferred toast ---
if "_discover_toast" in st.session_state:
    _toast_msg, _toast_icon = st.session_state.pop("_discover_toast")
    st.toast(_toast_msg, icon=_toast_icon)

# --- Load genre data for tag selection ---
# Genre map is needed for pills UI and resolving genre IDs on movie cards.
try:
    genre_map = get_genre_map()
except requests.HTTPError as e:
    if e.response is not None and e.response.status_code == 401:
        st.error(
            "Invalid TMDB API key. Check `.streamlit/secrets.toml`.",
            icon=":material/key_off:",
        )
    else:
        st.error("TMDB API error. Please try again later.", icon=":material/error:")
    st.stop()
except requests.ConnectionError:
    st.error(
        "Could not connect to TMDB. Check your internet connection.",
        icon=":material/wifi_off:",
    )
    st.stop()

# --- Phase management ---
# Two phases: "select" (genre tags) -> "browse" (movie cards)
st.session_state.setdefault("discover_phase", "select")
st.session_state.setdefault("discover_index", 0)


def _start_browsing() -> None:
    """Transition from genre selection to movie browsing."""
    # Save filter names for display on browse phase and restoration on back
    selected = list(st.session_state.get("genre_pills", []))
    st.session_state["_discover_saved_genres"] = selected
    # Reverse-lookup: resolve genre names back to TMDB genre IDs for the API call
    st.session_state["_discover_genres"] = tuple(sorted(
        gid for gid, name in genre_map.items() if name in (selected or [])
    ))
    # Switch to browse phase and reset movie position to the first result
    st.session_state.discover_phase = "browse"
    st.session_state.discover_index = 0


def _back_to_selection() -> None:
    """Return to genre selection phase, preserving filter state."""
    st.session_state.discover_phase = "select"
    # Restore pills widget state from saved selections so filters are not lost
    if "_discover_saved_genres" in st.session_state:
        st.session_state["genre_pills"] = st.session_state["_discover_saved_genres"]


# === PHASE 1: Genre Selection ===
if st.session_state.discover_phase == "select":
    # Genre pills — hard AND filter via TMDB API
    st.subheader("Genre")
    selected_genres = st.pills(
        "Genre",
        options=list(genre_map.values()),
        selection_mode="multi",
        key="genre_pills",
        label_visibility="collapsed",
    )

    # Button label adapts: "Search" with genres, "Show trending" without
    st.button(
        "Search" if selected_genres else "Show trending",
        icon=":material/search:",
        on_click=_start_browsing,
        type="primary",
    )
    st.stop()  # Halt rendering — only selection UI is shown in this phase

# === PHASE 2: Movie Browsing ===
# Retrieve genre IDs stored by _start_browsing callback
selected_ids = st.session_state.get("_discover_genres", ())

# Back button to return to genre selection
st.button("Change filters", icon=":material/arrow_back:", on_click=_back_to_selection)

# --- Active filter badges ---
# Show currently selected genres as inline badges
_active_genres = st.session_state.get("_discover_saved_genres", [])
if _active_genres:
    st.markdown(" ".join(f":gray-badge[{g}]" for g in _active_genres))

# --- Load movies with automatic pagination ---
dismissed = st.session_state.dismissed
watchlisted_ids = {m["id"] for m in st.session_state.watchlist}
rated_ids = st.session_state.ratings  # dict {movie_id: rating} — membership check is O(1)
available: list[dict] = []  # Accumulates unseen movies across pages

try:
    for page in range(1, 11):
        if selected_ids:
            movies = discover_movies(selected_ids, page=page)
        else:
            movies = get_trending(page=page)

        if not movies:
            break  # No more results from API

        # Filter out dismissed, watchlisted, and already-rated movies
        available.extend(
            m for m in movies
            if m["id"] not in dismissed
            and m["id"] not in watchlisted_ids
            and m["id"] not in rated_ids
        )

        # Stop at first available movie (no keyword ranking pool needed)
        if available:
            break
except requests.HTTPError as e:
    if e.response is not None and e.response.status_code == 401:
        st.error(
            "Invalid TMDB API key. Check `.streamlit/secrets.toml`.",
            icon=":material/key_off:",
        )
    else:
        st.error("TMDB API error. Please try again later.", icon=":material/error:")
    st.stop()
except requests.ConnectionError:
    st.error(
        "Could not connect to TMDB. Check your internet connection.",
        icon=":material/wifi_off:",
    )
    st.stop()

if not available:
    if selected_ids:
        st.info(
            "No movies found for these genres. Try selecting fewer tags!",
            icon=":material/search_off:",
        )
    else:
        st.info(
            "You have seen all trending movies! Check back later for new ones.",
            icon=":material/celebration:",
        )
    st.stop()

# --- Current movie card ---
# Modulo wraps the index to stay within bounds when the list shrinks
index = st.session_state.discover_index % len(available)
movie = available[index]

# Fetch full details for runtime and streaming providers (cached 1h)
_movie_details: dict | None = None
try:
    _movie_details = get_movie_details(movie["id"])
except requests.RequestException:
    pass  # Non-critical — card still works with basic data

# Resolve genre IDs to human-readable names
genre_names = [genre_map.get(gid, "Unknown") for gid in movie.get("genre_ids", [])]

# Card layout: poster on the left, info on the right
with st.container(border=True):
    col_poster, col_info = st.columns([1, 2])
    with col_poster:
        # w342 poster size for card display
        st.image(poster_url(movie.get("poster_path")), width=250)
    with col_info:
        st.subheader(movie["title"])
        # Genre section
        if genre_names:
            st.caption("**Genre**")
            st.markdown(" ".join(f":gray-badge[{g}]" for g in genre_names))
        # TMDB rating — 1 decimal for consistent display
        _tmdb = movie.get("vote_average")
        st.caption(f"TMDB rating: {_tmdb:.1f} / 10" if _tmdb else "TMDB rating: N/A")
        # Runtime (from details API, not available in discover/trending responses)
        if _movie_details:
            _runtime = _movie_details.get("runtime")
            if _runtime:
                _h, _m = divmod(_runtime, 60)
                st.caption(f":material/schedule: {_h}h {_m}min" if _h else f":material/schedule: {_m} min")
        st.write(movie.get("overview", "No description available."))
    # Streaming providers for Switzerland (from details API)
    if _movie_details:
        _providers = _movie_details.get("watch/providers", {}).get("results", {}).get("CH", {})
        _flatrate = _providers.get("flatrate", [])
        if _flatrate:
            st.markdown("**Streaming in Switzerland:** " + " ".join(
                f":{_PROVIDER_COLORS.get(p['provider_name'], _DEFAULT_PROVIDER_COLOR)}-badge[{p['provider_name']}]"
                for p in _flatrate
            ))

# --- Action buttons ---
# Watchlist and dismiss are separate actions that advance to the next movie.


def _add_to_watchlist() -> None:
    """Add current movie to watchlist and advance to next."""
    st.session_state.watchlist.append(movie)  # Update runtime state
    save_to_watchlist(movie)  # Persist full movie dict to SQLite
    st.session_state.discover_index += 1  # Advance to next movie on rerun
    st.session_state["_discover_toast"] = (
        f"Added **{movie['title']}** to watchlist", ":material/bookmark:",
    )


def _dismiss() -> None:
    """Mark current movie as dismissed and advance to next."""
    st.session_state.dismissed.add(movie["id"])  # Update runtime set
    save_dismissed(movie["id"])  # Persist dismissal to SQLite
    st.session_state.discover_index += 1  # Advance to next movie on rerun
    st.session_state["_discover_toast"] = (
        f"Skipped **{movie['title']}**", ":material/thumb_down:",
    )


with st.container(horizontal=True):
    st.button("Not interested", icon=":material/thumb_down:", on_click=_dismiss)
    st.button(
        "Add to watchlist", icon=":material/bookmark:",
        on_click=_add_to_watchlist, type="primary",
    )

# Movie counter — shows position within available results
st.caption(f"Movie {index + 1} of {len(available)}", text_alignment="center")
