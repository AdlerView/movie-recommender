"""Movie Recommender — Main entry point.

Configures the Streamlit app, initializes the database, loads persisted data
into session state, backfills missing movie details, and sets up multi-page
navigation with top positioning.
"""
from __future__ import annotations

import streamlit as st
from utils.db import (
    get_ratings_without_details,
    get_ratings_without_keywords,
    init_db,
    load_dismissed,
    load_ratings,
    load_watchlist,
    save_movie_details,
    save_movie_keywords,
)
from utils.tmdb import get_movie_details, get_movie_keywords

# Page config must be the first Streamlit command
st.set_page_config(
    page_title="Movie Recommender",
    page_icon=":material/movie:",
    layout="wide",
)

# --- Database initialization ---
# Create tables on first run (no-op if they already exist)
init_db()

# --- Global session state ---
# Load persisted data from SQLite on first run only.
# After loading, session state is the runtime source of truth.
# Pages write to both session state and DB on every action.
if "db_loaded" not in st.session_state:
    st.session_state.ratings = load_ratings()       # {movie_id: 0.00-10.00}
    st.session_state.watchlist = load_watchlist()    # [movie_dict, ...]
    st.session_state.dismissed = load_dismissed()    # {movie_id, ...}
    st.session_state.db_loaded = True

# --- Backfill movie details ---
# Fetch TMDB details for ratings that were saved before the movie_details
# table existed. Runs once per session; skips on subsequent reruns.
if "details_backfilled" not in st.session_state:
    missing_ids = get_ratings_without_details()
    if missing_ids:
        with st.spinner(f"Loading details for {len(missing_ids)} rated movies..."):
            for movie_id in missing_ids:
                try:
                    details = get_movie_details(movie_id)
                    save_movie_details(movie_id, details)
                except Exception:
                    pass  # Skip failed fetches — will retry next session
    st.session_state.details_backfilled = True

# --- Backfill movie keywords ---
# Fetch TMDB keywords for ratings that have details but no keywords yet.
# Keywords are fetched via a separate endpoint to avoid cache invalidation.
if "keywords_backfilled" not in st.session_state:
    missing_kw_ids = get_ratings_without_keywords()
    if missing_kw_ids:
        with st.spinner(f"Loading keywords for {len(missing_kw_ids)} rated movies..."):
            for movie_id in missing_kw_ids:
                try:
                    keywords = get_movie_keywords(movie_id)
                    save_movie_keywords(movie_id, keywords)
                except Exception:
                    pass  # Skip failed fetches — will retry next session
    st.session_state.keywords_backfilled = True

# --- Push Statistics tab to the far right of the nav bar ---
# The first 3 tabs (Discover, Watched, Watchlist) stay left-aligned;
# the 4th tab (Statistics) gets margin-left:auto to fill remaining space.
# Streamlit renders nav items as div.rc-overflow-item inside div.rc-overflow.
st.markdown("""<style>
    /* Make the nav overflow container span full toolbar width */
    [data-testid="stToolbar"] .rc-overflow {
        width: 100% !important;
    }
    /* Push 4th nav item (Statistics) to the far right */
    [data-testid="stToolbar"] .rc-overflow > .rc-overflow-item:nth-child(4) {
        margin-left: auto !important;
    }
</style>""", unsafe_allow_html=True)

# --- Navigation ---
# Top navigation: each tab has exactly one responsibility
# Discover = find new, Rate = rate watched, Watchlist = saved, Statistics = review
page = st.navigation(
    [
        st.Page("app_pages/discover.py", title="Discover", icon=":material/explore:"),
        st.Page("app_pages/rate.py", title="Rate", icon=":material/star:"),
        st.Page("app_pages/watchlist.py", title="Watchlist", icon=":material/bookmark:"),
        st.Page("app_pages/statistics.py", title="Statistics", icon=":material/bar_chart:"),
    ],
    position="top",
)

# Run the selected page
page.run()
