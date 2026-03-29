"""Watchlist page — poster grid, detail dialog, rate or remove. See VIEWS.md."""
from __future__ import annotations

import requests
import streamlit as st
from src.utils import GRID_COLS, fetch_and_cache_details
from src.utils.db import (
    remove_from_watchlist,
    save_mood_reactions,
    save_rating,
)
from src.utils.tmdb import get_movie_details, poster_url

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
    # "Discover more" button as actionable next step (same styling as Load more
    # on Discover/Rate: full container width, no icon)
    if st.button("Discover more", width="stretch", type="primary"):
        st.switch_page("src/views/discover.py")
    st.stop()


def _select_movie(movie_id: int) -> None:
    st.session_state._watchlist_selected = movie_id


# Dialog defined inline at trigger point below (dynamic title per movie).


# --- Clickable poster grid CSS (shared helper) ---
from src.utils import inject_poster_grid_css
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

# --- "Discover more" button (always shown after grid, mirrors Load more styling) ---
# Uses st.switch_page for environment-agnostic navigation (works on localhost
# and production domains without hardcoding URLs)
if st.button("Discover more", width="stretch", type="primary"):
    st.switch_page("src/views/discover.py")

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
        from src.utils import render_watchlist_detail
        render_watchlist_detail(_details)

        # Action buttons
        col_remove, col_watched = st.columns(2)
        with col_remove:
            if st.button("Remove from watchlist", icon=":material/delete:",
                         width="stretch"):
                st.session_state.watchlist = [
                    m for m in st.session_state.watchlist if m["id"] != _mid
                ]
                remove_from_watchlist(_mid)
                # Treat removal as a mild negative signal — add to dismissed
                # so the movie won't reappear on Discover/Rate and contributes
                # to the contra vector in the ML scoring profile.
                from src.utils.db import save_dismissed
                st.session_state.dismissed.add(_mid)
                save_dismissed(_mid)
                st.session_state._watchlist_selected = None
                st.session_state["_watchlist_toast"] = (
                    f"Removed **{_details.get('title', '')}** from watchlist"
                )
                st.rerun()
        with col_watched:
            if st.button("Mark as watched", icon=":material/visibility:",
                         type="primary", width="stretch"):
                st.session_state["_watchlist_show_rating"] = True

        # Rating widget (shown after "Mark as watched" click)
        if st.session_state.get("_watchlist_show_rating"):
            st.subheader("Rate this movie")
            from src.utils import render_rating_widget
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
