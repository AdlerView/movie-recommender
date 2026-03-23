"""Rated page — View and re-rate all rated movies.

Displays every movie the user has rated, with sliders to adjust ratings.
A movie appears here if it has been rated on the Discover page, regardless
of whether it is on the watchlist.
"""
from __future__ import annotations

import requests
import streamlit as st
from utils.db import save_rating
from utils.tmdb import get_movie_details, poster_url

st.header("Your ratings", divider="blue")

ratings = st.session_state.get("ratings", {})

# --- Empty state ---
if not ratings:
    st.info(
        "No ratings yet. Head to Discover to rate some movies!",
        icon=":material/star_border:",
    )
    st.stop()

# --- Build lookup of movie metadata ---
# Collect metadata from watchlist first, then fetch missing from TMDB.
watchlist = st.session_state.get("watchlist", [])
movie_lookup: dict[int, dict] = {m["id"]: m for m in watchlist}

# Fetch metadata for rated movies not in the watchlist
for movie_id in ratings:
    if movie_id not in movie_lookup:
        try:
            details = get_movie_details(movie_id)
            movie_lookup[movie_id] = details
        except requests.RequestException:
            # Graceful fallback — show what we have
            movie_lookup[movie_id] = {"id": movie_id, "title": f"Movie #{movie_id}"}

# --- Rated movie list with sliders ---
for movie_id, current_rating in ratings.items():
    movie = movie_lookup[movie_id]

    with st.container(border=True):
        col_poster, col_info = st.columns([1, 3])
        with col_poster:
            st.image(
                poster_url(movie.get("poster_path"), size="w185"), width=100
            )
        with col_info:
            st.subheader(movie.get("title", f"Movie #{movie_id}"))
            st.caption(
                f"TMDB rating: {movie.get('vote_average', 'N/A')} / 10"
            )

        # Slider for re-rating
        new_rating = st.slider(
            "Your rating",
            min_value=0.00,
            max_value=10.00,
            value=current_rating if current_rating is not None else 0.00,
            step=0.01,
            format="%.2f/10",
            key=f"rated_{movie_id}",
        )
        # Save only when the rating changes
        if new_rating != current_rating:
            st.session_state.ratings[movie_id] = new_rating
            save_rating(movie_id, new_rating)

st.caption(f"{len(ratings)} movie{'s' if len(ratings) != 1 else ''} rated")
