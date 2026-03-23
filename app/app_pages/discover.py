"""Discover page — Browse and rate movies one at a time.

Presents a card-based flow where users see one trending movie at a time.
Rate on a 0.00-10.00 scale (matching TMDB), add to watchlist, or dismiss.
Rating and watchlist are independent actions.
"""
from __future__ import annotations

import requests
import streamlit as st
from utils.db import save_dismissed, save_rating, save_to_watchlist
from utils.tmdb import get_genre_map, get_trending, poster_url

st.header("Discover movies", divider="blue")

# --- Load movie data ---
# Fetch trending movies as initial discovery content.
# Error handling at the UI layer, not inside cached functions.
try:
    movies = get_trending()
    genre_map = get_genre_map()
except requests.HTTPError as e:
    if e.response is not None and e.response.status_code == 401:
        st.error(
            "Invalid TMDB API key. Check `.streamlit/secrets.toml`.",
            icon=":material/key_off:",
        )
    else:
        st.error("TMDB API error. Please try again later.", icon=":material/error:")
    st.stop()
except requests.ConnectionError:
    st.error(
        "Could not connect to TMDB. Check your internet connection.",
        icon=":material/wifi_off:",
    )
    st.stop()

# --- Filter out already-seen movies ---
# Skip movies the user has already dismissed or added to watchlist
dismissed = st.session_state.dismissed
watchlisted_ids = {m["id"] for m in st.session_state.watchlist}
available = [
    m for m in movies
    if m["id"] not in dismissed and m["id"] not in watchlisted_ids
]

if not available:
    st.info(
        "You have seen all trending movies! Check back later for new ones.",
        icon=":material/celebration:",
    )
    st.stop()

# --- Current movie card ---
# Track which movie the user is viewing with a bounded index
st.session_state.setdefault("discover_index", 0)
index = st.session_state.discover_index % len(available)
movie = available[index]

# Resolve genre IDs to human-readable names
genre_names = [genre_map.get(gid, "Unknown") for gid in movie.get("genre_ids", [])]

# Card layout: poster on the left, info on the right
with st.container(border=True):
    col_poster, col_info = st.columns([1, 2])
    with col_poster:
        # w342 poster size for card display
        st.image(poster_url(movie.get("poster_path")), width=250)
    with col_info:
        st.subheader(movie["title"])
        # Genre badges for quick visual scanning
        if genre_names:
            st.markdown(" ".join(f":blue-badge[{g}]" for g in genre_names))
        st.caption(f"TMDB rating: {movie.get('vote_average', 'N/A')} / 10")
        st.write(movie.get("overview", "No description available."))

# --- Rating slider ---
# Decimal rating 0.00-10.00 in 0.01 steps, matching the TMDB scale.
# Slider allows setting the value in one drag. Independent of watchlist.
current_rating = st.session_state.ratings.get(movie["id"])

new_rating = st.slider(
    "Your rating",
    min_value=0.00,
    max_value=10.00,
    value=current_rating if current_rating is not None else 0.00,
    step=0.01,
    format="%.2f/10",
    key=f"rate_{movie['id']}",
)

# Save only when the user actually changes the rating
if new_rating != current_rating:
    st.session_state.ratings[movie["id"]] = new_rating
    save_rating(movie["id"], new_rating)

# --- Action buttons ---
# Watchlist and dismiss are separate actions that advance to the next movie.


def _add_to_watchlist() -> None:
    """Add current movie to watchlist and advance to next."""
    st.session_state.watchlist.append(movie)
    save_to_watchlist(movie)
    st.session_state.discover_index += 1


def _dismiss() -> None:
    """Mark current movie as dismissed and advance to next."""
    st.session_state.dismissed.add(movie["id"])
    save_dismissed(movie["id"])
    st.session_state.discover_index += 1


with st.container(horizontal=True):
    st.button("Not interested", icon=":material/thumb_down:", on_click=_dismiss)
    st.button(
        "Add to watchlist", icon=":material/bookmark:",
        on_click=_add_to_watchlist, type="primary",
    )

st.caption(f"Movie {index + 1} of {len(available)} available")
