"""Statistics page — Personal movie taste insights.

Engaging dashboard showing genre preferences, mood profile, rating behavior
analysis, favorite directors/actors with photos, and a sortable ratings table.

All data from local SQLite — zero API calls. Charts built with Altair.

Dependencies:
    app.utils: render_person_ranking (shared director/actor card renderer)
    app.utils.db: all statistics queries (genre, mood, ratings, directors, actors)
    app.utils.tmdb: poster_url for thumbnails (no API calls — uses cached data)
"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st
from app.utils import MOOD_COLORS, render_person_ranking
from app.utils.db import (
    load_genre_ratings,
    load_mood_distribution,
    load_rated_movies_table,
    load_stats_summary,
    load_top_actors,
    load_top_directors,
    load_user_vs_tmdb,
)

# --- Load aggregated stats from SQLite (single query with JOIN) ---
stats = load_stats_summary()

# --- Empty state: show a hint when the user hasn't done anything yet ---
if stats["rated_count"] == 0 and stats["watchlisted_count"] == 0:
    st.info(
        "Start discovering and rating movies to see your statistics here!",
        icon=":material/bar_chart:",
    )
    st.stop()

# ============================================================
# KPIs — headline metrics in a horizontal row
# ============================================================

# Convert total runtime from minutes to hours for readability
total_hours = stats["total_runtime_min"] / 60
avg_rating = stats["avg_rating"]

# Horizontal container: 4 bordered metric cards side by side
with st.container(horizontal=True):
    st.metric("Movies rated", stats["rated_count"], border=True)
    st.metric("Watch hours", f"{total_hours:.1f}h", border=True)
    st.metric("Avg rating", f"{avg_rating:.0f} / 100", border=True)
    st.metric("Watchlisted", stats["watchlisted_count"], border=True)

# ============================================================
# GENRE PREFERENCES — horizontal bar chart, colored by avg user rating
# ============================================================

# load_genre_ratings() returns (genre_name, count, avg_rating) via json_each()
genre_data = load_genre_ratings()

if genre_data:
    st.subheader("Genres", divider="gray")
    genre_df = pd.DataFrame(
        genre_data, columns=["Genre", "Movies", "Avg Rating"],
    )
    # Bar length = movie count, bar color = average user rating for that genre
    # 5-level color scale: red → orange → yellow → light green → green
    chart = alt.Chart(genre_df).mark_bar().encode(
        x=alt.X("Movies:Q", title="Movies"),
        y=alt.Y("Genre:N", sort="-x", title=None),  # Sort by count descending
        color=alt.Color(
            "Avg Rating:Q",
            scale=alt.Scale(
                domain=[0, 20, 40, 60, 80, 100],
                range=["#ff4b4b", "#ff4b4b", "#ffa421", "#e8c840", "#85cc5a", "#21c354"],
            ),
            legend=alt.Legend(title="Avg rating"),
        ),
        tooltip=["Genre", "Movies", "Avg Rating"],  # Interactive hover info
    )
    st.altair_chart(chart, width="stretch")

# ============================================================
# MOOD PROFILE — horizontal bar chart with emoji labels
# ============================================================

# load_mood_distribution() counts mood tags from user_rating_moods table
mood_data = load_mood_distribution()

if mood_data:
    st.subheader("Moods", divider="gray")
    # Map each Ekman mood to emoji for Y-axis labels
    _emoji = {
        "Happy": "😊", "Interested": "🤔", "Surprised": "😲",
        "Sad": "😢", "Disgusted": "🤢", "Afraid": "😨", "Angry": "😠",
    }
    mood_df = pd.DataFrame(mood_data, columns=["Mood", "Reactions"])
    # Prepend emoji to mood name for the Y-axis label
    mood_df["Label"] = mood_df["Mood"].map(
        lambda m: f"{_emoji.get(m, '')} {m}",
    )
    # Per-mood color from shared MOOD_COLORS (same colors as pills on Discover/Rate)
    chart = alt.Chart(mood_df).mark_bar().encode(
        x=alt.X("Reactions:Q", title="Reactions"),
        y=alt.Y("Label:N", sort="-x", title=None),  # Most-reacted mood on top
        color=alt.Color(
            "Mood:N",
            scale=alt.Scale(
                domain=list(MOOD_COLORS.keys()),
                range=list(MOOD_COLORS.values()),
            ),
            legend=None,  # Labels already contain emoji + name
        ),
        tooltip=["Mood", "Reactions"],
    )
    st.altair_chart(chart, width="stretch")

# ============================================================
# RATING BEHAVIOR — scatter plot: user rating vs TMDB rating
# ============================================================

# load_user_vs_tmdb() returns (tmdb_rating 0-10, user_rating 0-100, title)
user_vs_tmdb = load_user_vs_tmdb()

if user_vs_tmdb:
    st.subheader("You vs TMDB", divider="gray")
    scatter_df = pd.DataFrame(
        user_vs_tmdb, columns=["TMDB", "You", "Title"],
    )
    # Scale TMDB from 0-10 to 0-100 so both axes are comparable
    scatter_df["TMDB (scaled)"] = scatter_df["TMDB"] * 10
    # Deviation: positive = user rates higher than TMDB, negative = lower
    scatter_df["Diff"] = scatter_df["You"] - scatter_df["TMDB (scaled)"]

    # Diagonal reference line: "perfect agreement" where user = TMDB
    line_df = pd.DataFrame({"x": [0, 100], "y": [0, 100]})
    diagonal = alt.Chart(line_df).mark_line(
        strokeDash=[4, 4], color="gray", opacity=0.5,
    ).encode(x="x:Q", y="y:Q")

    # Scatter points: green = user rates higher, red = user rates lower
    points = alt.Chart(scatter_df).mark_circle(size=80).encode(
        x=alt.X(
            "TMDB (scaled):Q",
            title="TMDB (scaled to 100)",
            scale=alt.Scale(domain=[0, 100]),
        ),
        y=alt.Y(
            "You:Q",
            title="Your rating",
            scale=alt.Scale(domain=[0, 100]),
        ),
        color=alt.Color(
            "Diff:Q",
            scale=alt.Scale(
                domain=[-50, -20, 0, 20, 50],
                range=["#ff4b4b", "#ffa421", "#888888", "#85cc5a", "#21c354"],
            ),
            legend=None,  # Color meaning is intuitive from the diagonal
        ),
        tooltip=["Title", alt.Tooltip("TMDB:Q", format=".1f"), "You"],
    )

    # Linear regression trend line to show overall bias direction
    trend = points.transform_regression(
        "TMDB (scaled)", "You",
    ).mark_line(strokeDash=[2, 2], opacity=0.6)

    # Layer all three: diagonal + scatter points + trend line
    st.altair_chart(diagonal + points + trend, width="stretch")

# ============================================================
# FAVORITE DIRECTORS + ACTORS — side-by-side photo rankings
# ============================================================

# Top 5 by movie count, with average rating and profile photo
directors = load_top_directors()
actors = load_top_actors()

if directors or actors:
    # Two-column layout: directors on left, actors on right
    col_dir, col_act = st.columns(2)

    with col_dir:
        if directors:
            st.subheader("Favorite directors", divider="gray")
            # Shared helper renders photos + name + count + avg rating
            render_person_ranking(directors, "director")

    with col_act:
        if actors:
            st.subheader("Favorite actors", divider="gray")
            render_person_ranking(actors, "actor")

# ============================================================
# RATINGS — sortable table with all rated movies
# ============================================================

# load_rated_movies_table() joins user_ratings with movie_details
rated_rows = load_rated_movies_table()

if rated_rows:
    st.subheader("Ratings", divider="gray")

    # Build table data: scale TMDB from 0-10 → 0-100 for direct comparison.
    table_data = [
        {
            "Title": row.get("title") or f"Movie #{row['movie_id']}",
            "TMDB": round(row["vote_average"] * 10) if row.get("vote_average") is not None else None,
            "You": row["rating"],
        }
        for row in rated_rows
    ]
    df = pd.DataFrame(table_data)

    # Both columns on 0-100 scale for visual comparability.
    # ProgressColumn color is fixed (primaryColor), so color-coding
    # happens via the "You vs TMDB" scatter chart above.
    st.dataframe(
        df,
        column_config={
            "Title": st.column_config.TextColumn("Title"),
            "TMDB": st.column_config.ProgressColumn(
                "TMDB", min_value=0, max_value=100, format="%d",
            ),
            "You": st.column_config.ProgressColumn(
                "You", min_value=0, max_value=100, format="%d",
            ),
        },
        hide_index=True,
        width="stretch",
    )
