"""Watchlist page — View saved movies with their ratings and streaming providers.

Displays movies the user has added from the Discover page. Ratings are
shown as read-only values. To re-rate, use the Rated page. Each movie
shows flatrate streaming providers available in Switzerland.
"""
from __future__ import annotations

import requests
import streamlit as st
from utils.tmdb import get_watch_providers, poster_url

# Provider brand colors for badge styling
_PROVIDER_COLORS: dict[str, str] = {
    "Netflix": "red",
    "Amazon Prime Video": "blue",
    "Disney Plus": "green",
    "Apple TV Plus": "gray",
    "Paramount Plus": "orange",
}
_DEFAULT_PROVIDER_COLOR = "violet"

st.header("Your watchlist", divider="blue")

watchlist = st.session_state.get("watchlist", [])
ratings = st.session_state.get("ratings", {})

# --- Empty state ---
if not watchlist:
    st.info(
        "No movies in your watchlist yet. Head to Discover to find some!",
        icon=":material/bookmark_border:",
    )
    st.stop()

# --- Movie list with read-only ratings ---
for movie in watchlist:
    current_rating = ratings.get(movie["id"])

    with st.container(border=True):
        col_poster, col_info, col_rating = st.columns([1, 3, 1])
        with col_poster:
            # w185 poster size for compact list items
            st.image(poster_url(movie.get("poster_path"), size="w185"), width=100)
        with col_info:
            st.subheader(movie["title"])
            st.caption(f"TMDB rating: {movie.get('vote_average', 'N/A')} / 10")
            # Show flatrate streaming providers for Switzerland
            try:
                providers = get_watch_providers(movie["id"])
            except requests.RequestException:
                providers = []
            if providers:
                st.markdown(" ".join(
                    f":{_PROVIDER_COLORS.get(p['provider_name'], _DEFAULT_PROVIDER_COLOR)}-badge[{p['provider_name']}]"
                    for p in providers
                ))
        with col_rating:
            # Read-only display of the user's rating
            st.caption("Your rating")
            if current_rating is not None:
                st.markdown(f"**{current_rating:.2f} / 10**")
            else:
                st.markdown("**— / 10**")

st.caption(
    f"{len(watchlist)} movie{'s' if len(watchlist) != 1 else ''} in your watchlist"
)
