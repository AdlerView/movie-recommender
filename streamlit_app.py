"""Movie Recommender — Main entry point and Streamlit app configuration.

This module is the single entry point for the Streamlit application. It runs
on every page load / rerun and handles:

1. Page configuration (title, icon, layout) — must be the first st.* call
2. Database initialization (CREATE TABLE IF NOT EXISTS for all 8 tables)
3. Session state hydration (load ratings, watchlist, dismissed, subscriptions
   from SQLite into st.session_state on the first run of each session)
4. Detail backfill (fetch TMDB details for ratings without cached metadata)
5. CSS injection for right-aligned navigation tabs (Statistics, Settings)
6. Multi-page navigation setup (5 pages via st.navigation with top position)

Dependencies:
    app.utils.db: database initialization and data loading functions
    app.utils.tmdb: TMDB API client for detail backfill
"""
from __future__ import annotations

import requests
import streamlit as st
from app.utils.db import (
    get_ratings_without_details,
    init_db,
    load_dismissed,
    load_ratings,
    load_subscriptions,
    load_watchlist,
    save_movie_details,
)
from app.utils.tmdb import get_movie_details

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
    st.session_state.ratings = load_ratings()             # {movie_id: 0-100 int}
    st.session_state.watchlist = load_watchlist()         # [movie_dict, ...]
    st.session_state.dismissed = load_dismissed()         # {movie_id, ...}
    st.session_state.subscriptions = load_subscriptions() # {provider_id, ...}
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
                except requests.RequestException:
                    pass  # Skip failed fetches — will retry next session
    st.session_state.details_backfilled = True


# --- Push Statistics + Settings to the far right of the nav bar ---
# The first 3 tabs (Discover, Rate, Watchlist) stay left-aligned;
# the 4th tab (Statistics) gets margin-left:auto, Settings follows naturally.
# Streamlit renders nav items as div.rc-overflow-item inside div.rc-overflow.
st.html("""<style>
    [data-testid="stToolbar"] .rc-overflow {
        width: 100% !important;
    }
    [data-testid="stToolbar"] .rc-overflow > .rc-overflow-item:nth-child(4) {
        margin-left: auto !important;
    }
    .stMainBlockContainer {
        padding-top: 3.75rem !important;
    }
</style>""")

# --- Navigation ---
# Top navigation: each tab has exactly one responsibility
page = st.navigation(
    [
        st.Page("app/views/discover.py", title="Discover", icon=":material/explore:"),
        st.Page("app/views/rate.py", title="Rate", icon=":material/star:"),
        st.Page("app/views/watchlist.py", title="Watchlist", icon=":material/bookmark:"),
        st.Page("app/views/statistics.py", title="Statistics", icon=":material/bar_chart:"),
        st.Page("app/views/settings.py", title="Settings", icon=":material/settings:"),
    ],
    position="top",
)

# Run the selected page
page.run()
