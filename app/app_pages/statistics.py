"""Statistics page — View your movie activity statistics.

Displays aggregated metrics about watchlisted, rated, and dismissed movies.
Will be expanded with genre charts, watch hours, and director stats
for grading requirement 3 (data visualization).
"""
from __future__ import annotations

import streamlit as st

st.header("Your statistics", divider="blue")

# Read shared state
ratings = st.session_state.get("ratings", {})
watchlist = st.session_state.get("watchlist", [])
dismissed = st.session_state.get("dismissed", set())

# --- KPI metrics row ---
# Horizontal container for responsive metric cards
with st.container(horizontal=True):
    st.metric("Watchlisted", len(watchlist), border=True)
    st.metric("Rated", len(ratings), border=True)
    st.metric("Dismissed", len(dismissed), border=True)

# --- Average rating ---
if ratings:
    avg = sum(ratings.values()) / len(ratings)
    st.metric("Average rating", f"{avg:.2f} / 10", border=True)

# --- Empty state ---
if not ratings and not watchlist:
    st.info(
        "Start discovering movies to see your statistics here!",
        icon=":material/bar_chart:",
    )
