"""Movie Recommender — Main entry point.

Configures the Streamlit app, initializes the database, loads persisted data
into session state, and sets up multi-page navigation with top positioning.
"""
from __future__ import annotations

import streamlit as st
from utils.db import init_db, load_dismissed, load_ratings, load_watchlist

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

# --- Navigation ---
# Top navigation for 4 pages
page = st.navigation(
    [
        st.Page("app_pages/discover.py", title="Discover", icon=":material/explore:"),
        st.Page("app_pages/watchlist.py", title="Watchlist", icon=":material/bookmark:"),
        st.Page("app_pages/rated.py", title="Rated", icon=":material/star:"),
        st.Page("app_pages/statistics.py", title="Statistics", icon=":material/bar_chart:"),
    ],
    position="top",
)

# Run the selected page
page.run()
