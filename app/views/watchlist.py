"""Watchlist page — Poster grid of saved movies with detail dialog.

Displays movies the user has added from the Discover page as a Netflix-style
poster grid. Clicking a poster opens a dialog with TMDB rating, streaming
providers, and actions (remove from watchlist, mark as watched with rating
slider 0-100 and mood reactions).
"""
from __future__ import annotations

import sqlite3

import requests
import streamlit as st
from app.utils.db import (
    remove_from_watchlist,
    save_mood_reactions,
    save_movie_details,
    save_movie_keywords,
    save_rating,
)
from app.utils.tmdb import get_movie_details, get_movie_keywords, poster_url

# Provider brand colors for badge styling
_PROVIDER_COLORS: dict[str, str] = {
    "Netflix": "red",
    "Amazon Prime Video": "blue",
    "Disney Plus": "green",
    "Apple TV Plus": "gray",
    "Paramount Plus": "orange",
}
_DEFAULT_PROVIDER_COLOR = "violet"

# Number of columns in the poster grid (matches Rate page)
_GRID_COLS = 5

st.header("Your watchlist", divider="gray", text_alignment="center")

# --- Deferred toast ---
if "_watchlist_toast" in st.session_state:
    st.toast(st.session_state.pop("_watchlist_toast"), icon=":material/bookmark:")

# --- State management ---
st.session_state.setdefault("_watchlist_selected", None)

# Read shared state — loaded from SQLite on app start, updated on every action
watchlist: list[dict] = st.session_state.get("watchlist", [])

# --- Empty state ---
if not watchlist:
    st.info(
        "No movies in your watchlist yet. Head to Discover to find some!",
        icon=":material/bookmark_border:",
    )
    st.stop()


def _select_movie(movie_id: int) -> None:
    """Set the selected movie ID to trigger the detail dialog.

    Args:
        movie_id: TMDB movie ID to show details for.
    """
    st.session_state._watchlist_selected = movie_id


# --- Dialog: movie detail overlay ---
@st.dialog("Movie details", width="large")
def _show_detail(movie_id: int) -> None:
    """Render movie detail dialog with streaming info and actions.

    Args:
        movie_id: TMDB movie ID to display.
    """
    # Fetch full details (cached 1h) for runtime, genres, providers, overview
    try:
        details = get_movie_details(movie_id)
    except requests.RequestException:
        st.error("Could not load movie details.", icon=":material/error:")
        return

    # --- Movie info card ---
    col_poster, col_info = st.columns([1, 2])
    with col_poster:
        st.image(poster_url(details.get("poster_path"), size="w500"), width=250)
    with col_info:
        st.subheader(details.get("title", "Unknown"))
        # Genre section
        genres = details.get("genres", [])
        if genres:
            st.caption("**Genre**")
            st.markdown(" ".join(
                f":gray-badge[{g['name']}]" for g in genres
            ))
        # TMDB rating — 1 decimal for consistent display
        _tmdb = details.get("vote_average")
        st.caption(f"TMDB rating: {_tmdb:.1f} / 10" if _tmdb else "TMDB rating: N/A")
        # Runtime
        runtime = details.get("runtime")
        if runtime:
            hours, mins = divmod(runtime, 60)
            if hours:
                st.caption(f":material/schedule: {hours}h {mins}min")
            else:
                st.caption(f":material/schedule: {mins} min")
        # Overview
        st.write(details.get("overview", "No description available."))

    # --- Streaming providers (Switzerland) ---
    providers_data = details.get("watch/providers", {}).get("results", {}).get("CH", {})
    flatrate = providers_data.get("flatrate", [])
    if flatrate:
        st.markdown("**Streaming in Switzerland:** " + " ".join(
            f":{_PROVIDER_COLORS.get(p['provider_name'], _DEFAULT_PROVIDER_COLOR)}-badge[{p['provider_name']}]"
            for p in flatrate
        ))

    st.divider()

    # --- Actions ---
    col_remove, col_watched = st.columns(2)
    with col_remove:
        if st.button(
            "Remove from watchlist",
            icon=":material/delete:",
            use_container_width=True,
        ):
            # Remove from session state and database
            st.session_state.watchlist = [
                m for m in st.session_state.watchlist if m["id"] != movie_id
            ]
            remove_from_watchlist(movie_id)
            st.session_state._watchlist_selected = None
            st.session_state["_watchlist_toast"] = f"Removed **{details.get('title', '')}** from watchlist"
            st.rerun()

    with col_watched:
        if st.button(
            "Mark as watched",
            icon=":material/visibility:",
            type="primary",
            use_container_width=True,
        ):
            # Switch to rating mode inside the dialog
            st.session_state["_watchlist_show_rating"] = True

    # --- Rating widget (shown after "Mark as watched" click) ---
    if st.session_state.get("_watchlist_show_rating"):
        st.subheader("Rate this movie")
        from app.utils import render_rating_widget
        new_rating, selected_moods, _slider_ready = render_rating_widget(
            movie_id, key_prefix="wl",
        )

        if st.button("Save rating", type="primary", icon=":material/save:", disabled=not _slider_ready):
            # Save rating to session state and database
            st.session_state.ratings[movie_id] = new_rating
            save_rating(movie_id, new_rating)
            # Save mood reactions (empty list if none selected)
            save_mood_reactions(movie_id, list(selected_moods or []))
            # Eager fetch: cache full TMDB details + keywords for Statistics/ML
            try:
                save_movie_details(movie_id, details)
            except (requests.RequestException, sqlite3.Error):
                pass
            try:
                save_movie_keywords(movie_id, get_movie_keywords(movie_id))
            except (requests.RequestException, sqlite3.Error):
                pass
            # Remove from watchlist (watched = no longer on watchlist)
            st.session_state.watchlist = [
                m for m in st.session_state.watchlist if m["id"] != movie_id
            ]
            remove_from_watchlist(movie_id)
            # Clean up dialog state
            st.session_state._watchlist_selected = None
            st.session_state.pop("_watchlist_show_rating", None)
            st.session_state.pop(f"_wl_touched_{movie_id}", None)
            st.session_state["_watchlist_toast"] = (
                f"Rated **{details.get('title', '')}**: {new_rating}/100"
            )
            st.rerun()


# --- Clickable poster grid CSS (shared helper) ---
from app.utils import inject_poster_grid_css
inject_poster_grid_css("watchlist_grid")

# --- Poster grid ---
# Filter out movies without posters for visual consistency
# Deduplicate by movie ID to prevent DuplicateElementKey errors
_seen: set[int] = set()
grid_movies: list[dict] = []
for m in watchlist:
    if m.get("poster_path") and m["id"] not in _seen:
        grid_movies.append(m)
        _seen.add(m["id"])

with st.container(key="watchlist_grid"):
    for row_start in range(0, len(grid_movies), _GRID_COLS):
        row_movies = grid_movies[row_start:row_start + _GRID_COLS]
        cols = st.columns(_GRID_COLS)
        for col, movie in zip(cols, row_movies):
            with col:
                st.image(poster_url(movie.get("poster_path"), size="w342"))
                # Invisible button overlay — captures clicks on the poster
                st.button(
                    "Details",
                    key=f"wl_sel_{movie['id']}",
                    on_click=_select_movie,
                    args=(movie["id"],),
                )

# Footer: total count
st.caption(
    f"{len(watchlist)} movie{'s' if len(watchlist) != 1 else ''} in your watchlist"
)

# --- Trigger dialog after grid renders (dialog must be called in main flow) ---
if st.session_state._watchlist_selected is not None:
    _show_detail(st.session_state._watchlist_selected)
