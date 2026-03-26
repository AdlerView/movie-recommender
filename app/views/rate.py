"""Rate page — Search and rate movies you've already seen.

Find movies via TMDB text search or browse personalized recommendations, then rate them
on a 0-100 scale (steps of 10) with optional mood reactions. Clicking a
poster opens a detail dialog with rating slider and mood buttons. Pure
action tab — rated movies are reviewed on the Statistics page instead.
"""
from __future__ import annotations

import sqlite3

import requests
import streamlit as st
from app.utils.db import (
    save_mood_reactions,
    save_movie_details,
    save_movie_keywords,
    save_rating,
)
from app.utils.tmdb import (
    discover_movies_filtered,
    get_movie_details,
    get_movie_keywords,
    poster_url,
    search_movies,
)
from ml.scoring.scoring import score_candidates
from ml.scoring.user_profile import get_or_compute_profile

# Default discover params for the browse grid (same endpoint as Discover page)
_RATE_DISCOVER_PARAMS: tuple[tuple[str, str], ...] = (
    ("sort_by", "popularity.desc"),
    ("vote_count.gte", "50"),
)

st.header("Rate a movie", divider="gray", text_alignment="center")

# --- Deferred toast ---
# Shown after rerun following a save (st.toast before st.rerun is lost)
if "_watched_toast" in st.session_state:
    st.toast(st.session_state.pop("_watched_toast"), icon=":material/star:")

# --- State management ---
# _watched_selected_id: movie ID to show in the detail dialog (int or None)
st.session_state.setdefault("_watched_selected_id", None)
# Pagination: how many TMDB pages are loaded (20 movies per page)
st.session_state.setdefault("_watched_pages", 1)
# Track previous query to reset pagination when the search term changes
st.session_state.setdefault("_watched_prev_query", "")

# Number of columns in the poster grid
_GRID_COLS = 5
# TMDB returns 20 results per page — used to detect when no more pages exist
_TMDB_PAGE_SIZE = 20


def _select_movie_id(movie_id: int) -> None:
    """Set the selected movie ID to trigger the detail dialog.

    Args:
        movie_id: TMDB movie ID to show details for.
    """
    st.session_state._watched_selected_id = movie_id


def _load_more() -> None:
    """Load the next page of browse/search results."""
    st.session_state._watched_pages += 1



# --- Dialog: movie detail + rating overlay ---
@st.dialog("Rate movie", width="large")
def _show_rating_dialog(movie_id: int) -> None:
    """Render movie detail dialog with rating slider.

    Args:
        movie_id: TMDB movie ID to display and rate.
    """
    # Fetch full details (cached 1h) for runtime, genres, overview
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
            st.markdown(" ".join(f":gray-badge[{g['name']}]" for g in genres))
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

    st.divider()

    # --- Rating widget (shared: slider + sentiment label + color CSS + mood pills) ---
    current_rating = st.session_state.ratings.get(movie_id)
    from app.utils import render_rating_widget
    new_rating, selected_moods, _slider_ready = render_rating_widget(
        movie_id, key_prefix="rate", current_rating=current_rating,
    )

    if st.button("Save rating", type="primary", icon=":material/save:", disabled=not _slider_ready):
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
        st.session_state._watched_selected_id = None
        st.session_state.pop(f"_rate_touched_{movie_id}", None)
        st.session_state["_watched_toast"] = (
            f"Rated **{details.get('title', '')}**: {new_rating}/100"
        )
        st.rerun()


# === Search & Browse ===
# Search subheader with collapsed widget label for visual consistency
st.subheader("Search")
query = st.text_input(
    "Search",
    placeholder="e.g. Inception, The Matrix, Parasite...",
    key="watched_search",
    icon=":material/search:",
    label_visibility="collapsed",
)

# Normalize query for comparison and pagination reset
current_query = query.strip() if query else ""

# Reset pagination when the search term changes
if current_query != st.session_state._watched_prev_query:
    st.session_state._watched_pages = 1
    st.session_state._watched_prev_query = current_query

# Compute profile once (used for subheader + re-ranking below)
_profile = None if current_query else get_or_compute_profile(
    ratings=st.session_state.ratings,
)

if current_query:
    st.subheader("Search results")
elif _profile is not None:
    # Personalized browse: discover candidates re-ranked by ML scoring
    st.subheader("Based on your interests")
else:
    # Cold start: no ratings yet, show popular movies
    st.subheader("Discover movies")

# --- Fetch movies with pagination ---
# Loads pages until we have enough unrated movies to fill the grid.
# Rated movies are excluded (they appear in "Your ratings" below),
# so we may need extra pages to compensate for filtered-out entries.
rated_ids = st.session_state.get("ratings", {})
target_count = st.session_state._watched_pages * _TMDB_PAGE_SIZE
movies: list[dict] = []
has_more = True  # Whether more pages are available from TMDB
_max_pages = 10  # Safety cap to avoid excessive API calls

try:
    p = 0
    while len(movies) < target_count and has_more and p < _max_pages:
        p += 1
        if current_query:
            page_movies = search_movies(current_query, page=p)
        else:
            # Discover endpoint with default params (same as Discover page)
            response = discover_movies_filtered(_RATE_DISCOVER_PARAMS, page=p)
            page_movies = response.get("results", [])
        if not page_movies:
            has_more = False
            break
        # Filter per page: remove poster-less and duplicate movies.
        # Rated movies are excluded from browse (already rated = not actionable)
        # but kept in search results (allows re-rating via search).
        seen_ids = {m["id"] for m in movies}
        page_movies = [
            m for m in page_movies
            if m.get("poster_path") and m["id"] not in seen_ids
            and (current_query or m["id"] not in rated_ids)
        ]
        movies.extend(page_movies)
        # TMDB returns 20 per page; fewer means we've reached the last page
        if len(page_movies) < _TMDB_PAGE_SIZE:
            has_more = p < _max_pages
    # Trim to exact target count
    movies = movies[:target_count]

    # --- Personalized re-ranking (when profile exists, no search query) ---
    if not current_query and _profile is not None and movies:
        _scored = score_candidates(_profile, [m["id"] for m in movies])
        _id_to_score = {mid: score for mid, score in _scored}
        movies.sort(
            key=lambda m: _id_to_score.get(m["id"], 0.0), reverse=True,
        )

except requests.HTTPError:
    st.error("TMDB API error. Please try again later.", icon=":material/error:")
    st.stop()
except requests.ConnectionError:
    st.error(
        "Could not connect to TMDB. Check your internet connection.",
        icon=":material/wifi_off:",
    )
    st.stop()

if not movies:
    st.info(
        "No movies found. Try a different search term.",
        icon=":material/search_off:",
    )
    st.stop()

# --- Poster grid (Netflix-style: clickable poster images) ---
from app.utils import inject_poster_grid_css
inject_poster_grid_css("poster_grid")

with st.container(key="poster_grid"):
    for row_start in range(0, len(movies), _GRID_COLS):
        row_movies = movies[row_start:row_start + _GRID_COLS]
        cols = st.columns(_GRID_COLS)
        for col, movie in zip(cols, row_movies):
            with col:
                # Poster image (w342 for sharp display in 5-column grid)
                st.image(poster_url(movie.get("poster_path"), size="w342"))
                # Invisible button overlay — captures clicks on the poster
                st.button(
                    "Rate",
                    key=f"watched_sel_{movie['id']}",
                    on_click=_select_movie_id,
                    args=(movie["id"],),
                )

# --- Load more button ---
# Shown when TMDB has more pages of results available
if has_more:
    st.button(
        "Load more",
        icon=":material/expand_more:",
        on_click=_load_more,
        use_container_width=True,
    )

# --- Trigger dialog after page renders (dialog must be called in main flow) ---
if st.session_state._watched_selected_id is not None:
    _show_rating_dialog(st.session_state._watched_selected_id)
