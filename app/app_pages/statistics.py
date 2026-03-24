"""Statistics page — Dashboard with KPIs, genre chart, and top directors.

Displays aggregated metrics from the normalized movie_details tables.
All data is pre-cached in SQLite via eager fetch (on rating) and backfill
(on startup), so this page makes zero TMDB API calls.

Grading requirement 3: Data visualization.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from utils.db import load_genre_distribution, load_stats_summary, load_top_directors

st.header("Your statistics", divider="blue")

# --- Load aggregated data from SQLite ---
stats = load_stats_summary()

# --- Empty state ---
if stats["rated_count"] == 0 and stats["watchlisted_count"] == 0:
    st.info(
        "Start discovering and rating movies to see your statistics here!",
        icon=":material/bar_chart:",
    )
    st.stop()

# --- KPI metrics row ---
# Watch hours and average runtime from cached movie_details.runtime
total_hours = stats["total_runtime_min"] / 60

with st.container(horizontal=True):
    st.metric(
        "Watch hours",
        f"{total_hours:.1f}h",
        border=True,
    )
    st.metric(
        "Avg runtime",
        f"{stats['avg_runtime_min']} min",
        border=True,
    )
    st.metric("Rated", stats["rated_count"], border=True)
    st.metric(
        "Avg rating",
        f"{stats['avg_rating']:.2f} / 10",
        border=True,
    )

with st.container(horizontal=True):
    st.metric("Watchlisted", stats["watchlisted_count"], border=True)
    st.metric("Dismissed", stats["dismissed_count"], border=True)

# --- Genre distribution bar chart ---
genre_data = load_genre_distribution()

if genre_data:
    st.subheader("Genre distribution", divider="blue")
    # Build DataFrame for st.bar_chart (index = genre name, column = count)
    genre_df = pd.DataFrame(genre_data, columns=["Genre", "Movies"])
    st.bar_chart(genre_df, x="Genre", y="Movies", horizontal=True)

# --- Top directors ---
directors = load_top_directors()

if directors:
    st.subheader("Favorite directors", divider="blue")
    for rank, (name, count) in enumerate(directors, start=1):
        # Display as numbered list with movie count
        suffix = "movie" if count == 1 else "movies"
        st.markdown(f"**{rank}. {name}** — {count} {suffix}")
