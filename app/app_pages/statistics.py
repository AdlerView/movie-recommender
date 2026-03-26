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
    load_decade_distribution,
    load_genre_distribution,
    load_language_distribution,
    load_mood_distribution,
    load_rated_movies_table,
    load_rating_distribution,
    load_rating_history,
    load_stats_summary,
    load_top_actors,
    load_top_directors,
    load_user_vs_tmdb,
)
from utils.tmdb import poster_url

st.header("Your statistics", divider="gray", text_alignment="center")

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
        f"{stats['avg_rating']:.0f} / 100",
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

# --- Language distribution bar chart ---
lang_data = load_language_distribution()

if lang_data:
    st.subheader("Language distribution", divider="gray")
    lang_df = pd.DataFrame(lang_data, columns=["Language", "Movies"])
    chart = alt.Chart(lang_df).mark_bar().encode(
        x=alt.X("Movies:Q", title="Movies"),
        y=alt.Y("Language:N", sort="-x", title=None),
    )
    st.altair_chart(chart, use_container_width=True)

# --- Decade distribution bar chart ---
decade_data = load_decade_distribution()

if decade_data:
    st.subheader("Decade distribution", divider="gray")
    decade_df = pd.DataFrame(decade_data, columns=["Decade", "Movies"])
    # Explicit categorical order to preserve descending decade sort
    chart = alt.Chart(decade_df).mark_bar().encode(
        x=alt.X("Movies:Q", title="Movies"),
        y=alt.Y("Decade:N", sort=list(decade_df["Decade"]), title=None),
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

# --- User vs TMDB scatter plot ---
user_vs_tmdb = load_user_vs_tmdb()

if user_vs_tmdb:
    st.subheader("Your rating vs TMDB", divider="gray")
    scatter_df = pd.DataFrame(user_vs_tmdb, columns=["TMDB", "You", "Title"])
    # Scale TMDB 0-10 to 0-100 for comparable axes
    scatter_df["TMDB (scaled)"] = scatter_df["TMDB"] * 10
    # Diagonal reference line: points above = you rate higher than TMDB
    line_df = pd.DataFrame({"x": [0, 100], "y": [0, 100]})
    base_line = alt.Chart(line_df).mark_line(
        strokeDash=[4, 4], color="gray", opacity=0.5,
    ).encode(x="x:Q", y="y:Q")
    points = alt.Chart(scatter_df).mark_circle(size=60).encode(
        x=alt.X("TMDB (scaled):Q", title="TMDB rating (scaled to 100)", scale=alt.Scale(domain=[0, 100])),
        y=alt.Y("You:Q", title="Your rating", scale=alt.Scale(domain=[0, 100])),
        tooltip=["Title", "TMDB", "You"],
    )
    st.altair_chart(base_line + points, use_container_width=True)

# --- Rating distribution histogram ---
rating_values = load_rating_distribution()

if rating_values:
    st.subheader("Rating distribution", divider="gray")
    rating_df = pd.DataFrame({"Rating": rating_values})
    # Histogram with bins at each step of 10 (0-10, 10-20, ..., 90-100)
    chart = alt.Chart(rating_df).mark_bar().encode(
        x=alt.X("Rating:Q", bin=alt.Bin(step=10), title="Rating (0-100)"),
        y=alt.Y("count()", title="Movies"),
    )
    st.altair_chart(chart, use_container_width=True)

# --- Rating history line chart ---
rating_history = load_rating_history()

if len(rating_history) >= 2:
    st.subheader("Rating history", divider="gray")
    history_df = pd.DataFrame(rating_history, columns=["Date", "Rating"])
    history_df["Date"] = pd.to_datetime(history_df["Date"])
    # Add sequential index for x-axis (movie #1, #2, ...) since multiple
    # ratings may share the same timestamp
    history_df["Movie #"] = range(1, len(history_df) + 1)
    chart = alt.Chart(history_df).mark_line(point=True).encode(
        x=alt.X("Movie #:Q", title="Movie #"),
        y=alt.Y("Rating:Q", title="Rating", scale=alt.Scale(domain=[0, 100])),
        tooltip=["Movie #", "Rating", "Date"],
    )
    st.altair_chart(chart, use_container_width=True)

# --- Mood distribution bar chart ---
mood_data = load_mood_distribution()

if mood_data:
    st.subheader("Mood distribution", divider="gray")
    mood_df = pd.DataFrame(mood_data, columns=["Mood", "Reactions"])
    chart = alt.Chart(mood_df).mark_bar().encode(
        x=alt.X("Reactions:Q", title="Reactions"),
        y=alt.Y("Mood:N", sort="-x", title=None),
    )
    st.altair_chart(chart, use_container_width=True)

# --- Top actors ---
actors = load_top_actors()

if actors:
    st.subheader("Favorite actors", divider="gray")
    for rank, (name, count) in enumerate(actors, start=1):
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
            "TMDB": round(row["vote_average"], 1) if row.get("vote_average") is not None else None,
            "Your rating": row["rating"],
        })

    df = pd.DataFrame(table_data)

    # Sortable interactive dataframe with poster thumbnails
    st.dataframe(
        df,
        column_config={
            "Poster": st.column_config.ImageColumn("", width="small"),
            "Title": st.column_config.TextColumn("Title"),
            "Duration": st.column_config.TextColumn("Duration"),
            "TMDB": st.column_config.NumberColumn("TMDB", format="%.1f", width="small"),
            "Your rating": st.column_config.NumberColumn(
                "Your rating", format="%d", width="small",
            ),
        },
        hide_index=True,
        use_container_width=True,
        row_height=50,
    )
