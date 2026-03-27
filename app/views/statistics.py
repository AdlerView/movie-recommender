"""Statistics page — Personal movie taste insights.

Engaging dashboard showing genre preferences, mood profile, rating behavior
analysis, favorite directors/actors with photos, and a sortable ratings table.

All data from local SQLite — zero API calls.
"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st
from app.utils.db import (
    load_genre_ratings,
    load_mood_distribution,
    load_rated_movies_table,
    load_stats_summary,
    load_top_actors,
    load_top_directors,
    load_user_vs_tmdb,
)
from app.utils.tmdb import poster_url

st.header("Your statistics", divider="gray", text_alignment="center")

# --- Load all data upfront ---
stats = load_stats_summary()

# --- Empty state ---
if stats["rated_count"] == 0 and stats["watchlisted_count"] == 0:
    st.info(
        "Start discovering and rating movies to see your statistics here!",
        icon=":material/bar_chart:",
    )
    st.stop()

# ============================================================
# KPIs
# ============================================================

total_hours = stats["total_runtime_min"] / 60
avg_rating = stats["avg_rating"]

with st.container(horizontal=True):
    st.metric("Movies rated", stats["rated_count"], border=True)
    st.metric("Watch hours", f"{total_hours:.1f}h", border=True)
    st.metric("Avg rating", f"{avg_rating:.0f} / 100", border=True)
    st.metric("Watchlisted", stats["watchlisted_count"], border=True)

# ============================================================
# GENRE PREFERENCES — full width, colored by avg rating
# ============================================================

genre_data = load_genre_ratings()

if genre_data:
    st.subheader("Your genres", divider="gray")
    genre_df = pd.DataFrame(
        genre_data, columns=["Genre", "Movies", "Avg Rating"],
    )
    chart = alt.Chart(genre_df).mark_bar().encode(
        x=alt.X("Movies:Q", title="Movies"),
        y=alt.Y("Genre:N", sort="-x", title=None),
        color=alt.Color(
            "Avg Rating:Q",
            scale=alt.Scale(
                domain=[0, 50, 100],
                range=["#ff4b4b", "#ffa421", "#21c354"],
            ),
            legend=alt.Legend(title="Your avg"),
        ),
        tooltip=["Genre", "Movies", "Avg Rating"],
    )
    st.altair_chart(chart, use_container_width=True)

# ============================================================
# MOOD PROFILE — full width, with emojis
# ============================================================

mood_data = load_mood_distribution()

if mood_data:
    st.subheader("Your moods", divider="gray")
    _emoji = {
        "Happy": "😊", "Interested": "🤔", "Surprised": "😲",
        "Sad": "😢", "Disgusted": "🤢", "Afraid": "😨", "Angry": "😠",
    }
    mood_df = pd.DataFrame(mood_data, columns=["Mood", "Reactions"])
    mood_df["Label"] = mood_df["Mood"].map(
        lambda m: f"{_emoji.get(m, '')} {m}",
    )
    chart = alt.Chart(mood_df).mark_bar().encode(
        x=alt.X("Reactions:Q", title="Reactions"),
        y=alt.Y("Label:N", sort="-x", title=None),
        tooltip=["Mood", "Reactions"],
    )
    st.altair_chart(chart, use_container_width=True)

# ============================================================
# RATING BEHAVIOR — You vs TMDB + distribution side-by-side
# ============================================================

user_vs_tmdb = load_user_vs_tmdb()

if user_vs_tmdb:
    st.subheader("You vs TMDB", divider="gray")
    scatter_df = pd.DataFrame(
        user_vs_tmdb, columns=["TMDB", "You", "Title"],
    )
    scatter_df["TMDB (scaled)"] = scatter_df["TMDB"] * 10
    scatter_df["Diff"] = scatter_df["You"] - scatter_df["TMDB (scaled)"]
    # Diagonal reference line
    line_df = pd.DataFrame({"x": [0, 100], "y": [0, 100]})
    diagonal = alt.Chart(line_df).mark_line(
        strokeDash=[4, 4], color="gray", opacity=0.5,
    ).encode(x="x:Q", y="y:Q")
    # Points colored by deviation from diagonal
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
                domain=[-50, 0, 50],
                range=["#ff4b4b", "#888888", "#21c354"],
            ),
            legend=None,
        ),
        tooltip=["Title", alt.Tooltip("TMDB:Q", format=".1f"), "You"],
    )
    trend = points.transform_regression(
        "TMDB (scaled)", "You",
    ).mark_line(strokeDash=[2, 2], opacity=0.6)
    st.altair_chart(diagonal + points + trend, use_container_width=True)

# ============================================================
# FAVORITE DIRECTORS + ACTORS — photos with stats
# ============================================================

directors = load_top_directors()
actors = load_top_actors()

if directors or actors:
    col_dir, col_act = st.columns(2)

    with col_dir:
        if directors:
            st.subheader("Favorite directors", divider="gray")
            _dcols = st.columns(len(directors))
            for i, d in enumerate(directors):
                with _dcols[i]:
                    _photo = poster_url(d["profile_path"], size="w185")
                    if _photo:
                        st.image(_photo, width=100)
                    st.caption(
                        f"**{d['name']}**  \n"
                        f"{d['movies']} {'movie' if d['movies'] == 1 else 'movies'}"
                        f" · {d['avg_rating']:.0f}/100",
                    )

    with col_act:
        if actors:
            st.subheader("Favorite actors", divider="gray")
            _acols = st.columns(len(actors))
            for i, a in enumerate(actors):
                with _acols[i]:
                    _photo = poster_url(a["profile_path"], size="w185")
                    if _photo:
                        st.image(_photo, width=100)
                    st.caption(
                        f"**{a['name']}**  \n"
                        f"{a['movies']} {'movie' if a['movies'] == 1 else 'movies'}"
                        f" · {a['avg_rating']:.0f}/100",
                    )

# ============================================================
# YOUR RATINGS — sortable table
# ============================================================

rated_rows = load_rated_movies_table()

if rated_rows:
    st.subheader("Your ratings", divider="gray")

    table_data = [
        {
            "Title": row.get("title") or f"Movie #{row['movie_id']}",
            "TMDB": round(row["vote_average"], 1) if row.get("vote_average") is not None else None,
            "Your rating": row["rating"],
        }
        for row in rated_rows
    ]

    df = pd.DataFrame(table_data)

    st.dataframe(
        df,
        column_config={
            "Title": st.column_config.TextColumn("Title"),
            "TMDB": st.column_config.NumberColumn(
                "TMDB", format="%.1f", width="small",
            ),
            "Your rating": st.column_config.ProgressColumn(
                "Your rating", min_value=0, max_value=100, format="%d",
            ),
        },
        hide_index=True,
        use_container_width=True,
    )
