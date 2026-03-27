"""Watchlist page — Poster grid of saved movies with detail dialog.

Displays movies the user has added from the Discover page as a Netflix-style
poster grid. Clicking a poster opens a dialog with TMDB rating, streaming
providers, and actions (remove from watchlist, mark as watched with rating
slider 0-100 and mood reactions).

Dependencies:
    app.utils: shared constants, CSS injection, detail renderer, rating widget,
        cache helper
    app.utils.db: watchlist and rating persistence
    app.utils.tmdb: TMDB API client (movie details, poster URLs)
"""
from __future__ import annotations

import requests
import streamlit as st
from app.utils import GRID_COLS, fetch_and_cache_details
from app.utils.db import (
    remove_from_watchlist,
    save_mood_reactions,
    save_rating,
)
from app.utils.tmdb import get_movie_details, poster_url

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


# Dialog defined inline at trigger point below (dynamic title per movie).


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
    for row_start in range(0, len(grid_movies), GRID_COLS):
        row_movies = grid_movies[row_start:row_start + GRID_COLS]
        cols = st.columns(GRID_COLS)
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

# --- Trigger dialog after grid renders (dialog must be called in main flow) ---
# Dialog defined inline so the movie title can be used as the dialog header.
if st.session_state._watchlist_selected is not None:
    _mid = st.session_state._watchlist_selected
    try:
        _details = get_movie_details(_mid)
    except requests.RequestException:
        st.error("Could not load movie details.", icon=":material/error:")
        st.stop()

    @st.dialog(_details.get("title", "Movie details"), width="large")
    def _show_watchlist_dialog() -> None:
        """Watchlist dialog: runtime + providers, trailer, watch now, actions."""
        from app.utils import render_watchlist_detail
        render_watchlist_detail(_details)

        # Action buttons
        col_remove, col_watched = st.columns(2)
        with col_remove:
            if st.button("Remove from watchlist", icon=":material/delete:",
                         use_container_width=True):
                st.session_state.watchlist = [
                    m for m in st.session_state.watchlist if m["id"] != _mid
                ]
                remove_from_watchlist(_mid)
                st.session_state._watchlist_selected = None
                st.session_state["_watchlist_toast"] = (
                    f"Removed **{_details.get('title', '')}** from watchlist"
                )
                st.rerun()
        with col_watched:
            if st.button("Mark as watched", icon=":material/visibility:",
                         type="primary", use_container_width=True):
                st.session_state["_watchlist_show_rating"] = True

        # Rating widget (shown after "Mark as watched" click)
        if st.session_state.get("_watchlist_show_rating"):
            st.subheader("Rate this movie")
            from app.utils import render_rating_widget
            new_rating, selected_moods, _slider_ready = render_rating_widget(
                _mid, key_prefix="wl",
            )
            if st.button("Save rating", type="primary", icon=":material/save:",
                         disabled=not _slider_ready):
                st.session_state.ratings[_mid] = new_rating
                save_rating(_mid, new_rating)
                save_mood_reactions(_mid, list(selected_moods or []))
                fetch_and_cache_details(_mid, _details)
                st.session_state.watchlist = [
                    m for m in st.session_state.watchlist if m["id"] != _mid
                ]
                remove_from_watchlist(_mid)
                st.session_state._watchlist_selected = None
                st.session_state.pop("_watchlist_show_rating", None)
                st.session_state.pop(f"_wl_touched_{_mid}", None)
                st.session_state["_watchlist_toast"] = (
                    f"Rated **{_details.get('title', '')}**: {new_rating}/100"
                )
                st.rerun()

    _show_watchlist_dialog()
