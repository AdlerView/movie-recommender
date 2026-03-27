"""Rate page — Search and rate movies you've already seen.

Find movies via TMDB text search or browse personalized recommendations,
then rate them on a 0-100 scale (steps of 10) with optional mood reactions.
Clicking a poster opens a detail dialog with rating slider and mood buttons.
Pure action tab — rated movies are reviewed on the Statistics page instead.

Browse grid uses the same TMDB discover/movie endpoint as Discover page
(unified retrieval layer), re-ranked by ML scoring when a profile exists.

Dependencies:
    app.utils: shared constants, CSS injection, rating widget, cache helper
    app.utils.db: rating and mood persistence
    app.utils.tmdb: TMDB API client (discover, search, details)
    ml.scoring: user profile computation, personalized scoring
"""
from __future__ import annotations

import requests
import streamlit as st
from app.utils import GRID_COLS, TMDB_PAGE_SIZE, fetch_and_cache_details
from app.utils.db import (
    save_mood_reactions,
    save_rating,
)
from app.utils.tmdb import (
    discover_movies_filtered,
    get_movie_details,
    poster_url,
    search_movies,
)
from ml.scoring import get_or_compute_profile, score_candidates

# Default discover params for the browse grid (same endpoint as Discover page)
_RATE_DISCOVER_PARAMS: tuple[tuple[str, str], ...] = (
    ("sort_by", "popularity.desc"),
    ("vote_count.gte", "50"),
)

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


def _select_movie_id(movie_id: int) -> None:
    """Set the selected movie ID to trigger the detail dialog.

    Args:
        movie_id: TMDB movie ID to show details for.
    """
    st.session_state._watched_selected_id = movie_id


def _load_more() -> None:
    """Load the next page of browse/search results."""
    st.session_state._watched_pages += 1



# Dialog defined inline at trigger point below (dynamic title per movie).


# === Search & Browse ===
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

# Compute profile once (used for section label + re-ranking below)
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
# Two modes: search (text query → search/movie API) or browse (no query →
# discover/movie API, same unified retrieval layer as Discover page).
# Loads pages until we have enough movies to fill the grid. May need extra
# pages because rated/dismissed/watchlisted movies are filtered out locally.
rated_ids = st.session_state.get("ratings", {})
target_count = st.session_state._watched_pages * TMDB_PAGE_SIZE
movies: list[dict] = []
has_more = True   # Whether TMDB has more pages available
_max_pages = 10   # Safety cap to avoid excessive API calls

try:
    p = 0
    while len(movies) < target_count and has_more and p < _max_pages:
        p += 1
        if current_query:
            # Search mode: GET /search/movie?query=...
            page_movies = search_movies(current_query, page=p)
        else:
            # Browse mode: GET /discover/movie with popularity sort
            # Same endpoint as Discover page (unified retrieval layer)
            response = discover_movies_filtered(_RATE_DISCOVER_PARAMS, page=p)
            page_movies = response.get("results", [])
        if not page_movies:
            has_more = False
            break

        # Per-page filtering logic:
        # - Browse grid: exclude rated + dismissed + watchlisted (same as Discover)
        # - Search results: keep rated movies (allows re-rating via search)
        # Both modes exclude poster-less movies and cross-page duplicates
        seen_ids = {m["id"] for m in movies}
        _dismissed = st.session_state.dismissed
        _watchlisted_ids = {m["id"] for m in st.session_state.watchlist}
        page_movies = [
            m for m in page_movies
            if m.get("poster_path") and m["id"] not in seen_ids
            and (current_query or (       # Search: keep everything
                m["id"] not in rated_ids  # Browse: exclude rated
                and m["id"] not in _dismissed       # Browse: exclude dismissed
                and m["id"] not in _watchlisted_ids # Browse: exclude watchlisted
            ))
        ]
        movies.extend(page_movies)
        # TMDB returns 20 results per full page; fewer = last page
        if len(page_movies) < TMDB_PAGE_SIZE:
            has_more = p < _max_pages

    # Trim to exact target count (may have fetched slightly more)
    movies = movies[:target_count]

    # --- Personalized re-ranking (browse mode only, when profile exists) ---
    # Uses the same 10-signal scoring as Discover page. No mood filter on Rate
    # (mood pills are only on Discover). Falls back to API popularity order
    # when no profile exists (cold start: 0 ratings).
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
    for row_start in range(0, len(movies), GRID_COLS):
        row_movies = movies[row_start:row_start + GRID_COLS]
        cols = st.columns(GRID_COLS)
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
        type="primary",
    )

# --- Trigger dialog after page renders (dialog must be called in main flow) ---
# Dialog defined inline so the movie title can be used as the dialog header.
if st.session_state._watched_selected_id is not None:
    _mid = st.session_state._watched_selected_id
    try:
        _details = get_movie_details(_mid)
    except requests.RequestException:
        st.error("Could not load movie details.", icon=":material/error:")
        st.stop()

    @st.dialog(_details.get("title", "Rate movie"), width="small")
    def _show_rating_dialog() -> None:
        """Rate dialog: minimal — just rating slider + moods."""
        current_rating = st.session_state.ratings.get(_mid)
        from app.utils import render_rating_widget
        new_rating, selected_moods, _slider_ready = render_rating_widget(
            _mid, key_prefix="rate", current_rating=current_rating,
        )

        if st.button("Save rating", type="primary", icon=":material/save:",
                     disabled=not _slider_ready):
            st.session_state.ratings[_mid] = new_rating
            save_rating(_mid, new_rating)
            save_mood_reactions(_mid, list(selected_moods or []))
            fetch_and_cache_details(_mid, _details)
            st.session_state._watched_selected_id = None
            st.session_state.pop(f"_rate_touched_{_mid}", None)
            st.session_state["_watched_toast"] = (
                f"Rated **{_details.get('title', '')}**: {new_rating}/100"
            )
            st.rerun()

    _show_rating_dialog()
