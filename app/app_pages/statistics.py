"""Statistics page — Dashboard with KPIs, genre chart, directors, and ratings table.

Displays aggregated metrics and a sortable table of all rated movies.
All data is pre-cached in SQLite via eager fetch (on rating) and backfill
(on startup), so this page makes zero TMDB API calls.

Grading requirement 3: Data visualization.
"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st
from utils.db import (
    load_genre_distribution,
    load_rated_movies_table,
    load_stats_summary,
    load_top_directors,
)
from utils.tmdb import poster_url

st.header("Your statistics", divider="gray")

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
    st.subheader("Genre distribution", divider="gray")
    # Build DataFrame — SQL already returns rows sorted by count descending
    genre_df = pd.DataFrame(genre_data, columns=["Genre", "Movies"])
    # Altair horizontal bar chart with explicit sort by frequency descending
    chart = alt.Chart(genre_df).mark_bar().encode(
        x=alt.X("Movies:Q", title="Movies"),
        y=alt.Y("Genre:N", sort="-x", title=None),
    )
    st.altair_chart(chart, use_container_width=True)

# --- Top directors ---
directors = load_top_directors()

if directors:
    st.subheader("Favorite directors", divider="gray")
    for rank, (name, count) in enumerate(directors, start=1):
        # Display as numbered list with movie count
        suffix = "movie" if count == 1 else "movies"
        st.markdown(f"**{rank}. {name}** — {count} {suffix}")

# --- Rated movies table ---
# Compact sortable table with thumbnail, title, duration, and ratings.
rated_rows = load_rated_movies_table()

if rated_rows:
    st.subheader("Your ratings", divider="gray")

    # Build DataFrame with display-ready columns
    table_data = []
    for row in rated_rows:
        # Format runtime as "Xh Ymin"
        runtime = row.get("runtime")
        if runtime:
            h, m = divmod(runtime, 60)
            duration = f"{h}h {m}min" if h else f"{m} min"
        else:
            duration = "—"

        table_data.append({
            "Poster": poster_url(row.get("poster_path"), size="w92") or "",
            "Title": row.get("title") or f"Movie #{row['movie_id']}",
            "Duration": duration,
            "TMDB": round(row["vote_average"], 1) if row.get("vote_average") else None,
            "Your rating": round(row["rating"], 2),
        })

    df = pd.DataFrame(table_data)

    # Sortable interactive dataframe with poster thumbnails
    st.dataframe(
        df,
        column_config={
            "Poster": st.column_config.ImageColumn("", width="small"),
            "Title": st.column_config.TextColumn("Title"),
            "Duration": st.column_config.TextColumn("Duration"),
            "TMDB": st.column_config.NumberColumn("TMDB", format="%.1f"),
            "Your rating": st.column_config.NumberColumn(
                "Your rating", format="%.2f",
            ),
        },
        hide_index=True,
        use_container_width=True,
        row_height=50,
    )
