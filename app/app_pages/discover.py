"""Discover page — Browse and rate movies by genre.

Two-phase flow: first select genre tags, then browse filtered movies one at a
time in a card-based flow. Rate on a 0.00-10.00 scale (matching TMDB), add to
watchlist, or dismiss. When no genres are selected, trending movies are shown.
"""
from __future__ import annotations

import requests
import streamlit as st
from utils.db import save_dismissed, save_rating, save_to_watchlist
from utils.tmdb import discover_movies, get_genre_map, get_trending, poster_url

# Header changes based on phase: genre selection vs. movie browsing
if st.session_state.get("discover_phase", "select") == "select":
    st.header("Which movie will you watch?", divider="blue")
else:
    st.header("Discover movies", divider="blue")

# --- Load genre data for tag selection ---
# Genre map is needed for pills UI and resolving genre IDs on movie cards.
try:
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

# --- Phase management ---
# Two phases: "select" (genre tags) → "browse" (movie cards)
st.session_state.setdefault("discover_phase", "select")
st.session_state.setdefault("discover_index", 0)


def _start_browsing() -> None:
    """Transition from genre selection to movie browsing."""
    # Read current pill selection from widget state (st.pills stores its value here)
    selected = st.session_state.get("genre_pills", [])
    # Reverse-lookup: resolve genre names back to TMDB genre IDs for the API call
    st.session_state["_discover_genres"] = tuple(sorted(
        gid for gid, name in genre_map.items() if name in (selected or [])
    ))
    # Switch to browse phase and reset movie position to the first result
    st.session_state.discover_phase = "browse"
    st.session_state.discover_index = 0


def _back_to_genres() -> None:
    """Return to genre selection phase."""
    st.session_state.discover_phase = "select"


# === PHASE 1: Genre Selection ===
if st.session_state.discover_phase == "select":
    # Pills for tag-like genre filtering (matches wireframe prototype)
    selected_genres = st.pills(
        "I want to watch something",
        options=list(genre_map.values()),
        selection_mode="multi",
        key="genre_pills",
    )

    # Button label adapts: "Search" with genres selected, "Show trending" without
    st.button(
        "Search" if selected_genres else "Show trending",
        icon=":material/search:",
        on_click=_start_browsing,
        type="primary",
    )
    st.stop()  # Halt rendering — only genre selection is shown in this phase

# === PHASE 2: Movie Browsing ===
# Retrieve genre IDs stored by _start_browsing callback; empty tuple = trending
selected_ids = st.session_state.get("_discover_genres", ())

# Back button to return to genre selection
st.button("Change genres", icon=":material/arrow_back:", on_click=_back_to_genres)

# --- Load movies with automatic pagination ---
# Fetches pages until available (unseen) movies are found, up to 10 pages.
# Each page is cached individually, so revisiting exhausted pages is instant.
# Build sets of already-seen movie IDs for fast lookup during filtering
dismissed = st.session_state.dismissed
watchlisted_ids = {m["id"] for m in st.session_state.watchlist}
available: list[dict] = []  # Accumulates unseen movies across pages

try:
    for page in range(1, 11):
        if selected_ids:
            movies = discover_movies(selected_ids, page=page)
        else:
            movies = get_trending(page=page)

        if not movies:
            break  # No more results from API

        # Filter out dismissed and watchlisted movies
        available.extend(
            m for m in movies
            if m["id"] not in dismissed and m["id"] not in watchlisted_ids
        )

        if available:
            break  # Found movies to show
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

if not available:
    if selected_ids:
        st.info(
            "No movies found for these genres. Try selecting fewer tags!",
            icon=":material/search_off:",
        )
    else:
        st.info(
            "You have seen all trending movies! Check back later for new ones.",
            icon=":material/celebration:",
        )
    st.stop()

# --- Current movie card ---
# Modulo wraps the index to stay within bounds when the list shrinks
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

# Dynamic slider color: gray (0), red (≤3.33), orange (≤6.66), green (>6.66)
if new_rating == 0.00:
    _slider_color = "#d3d3d3"
elif new_rating <= 3.33:
    _slider_color = "#ff4b4b"
elif new_rating <= 6.66:
    _slider_color = "#ffa421"
else:
    _slider_color = "#21c354"

# Inject CSS to override Streamlit's default slider styling
st.markdown(
    f"""<style>
    /* Track fill color — changes with rating value */
    .stSlider > div > div > div > div {{
        background: {_slider_color} !important;
    }}
    /* Thumb (draggable dot) — always black */
    .stSlider [role="slider"] {{
        background-color: #000 !important;
        border-color: #000 !important;
    }}
    /* Focus ring on drag — black instead of Streamlit's default red */
    .stSlider [role="slider"]:focus,
    .stSlider [role="slider"]:active {{
        box-shadow: 0 0 0 0.2rem rgba(0, 0, 0, 0.2) !important;
        outline: none !important;
    }}
    /* Score text above thumb — always black */
    .stSlider [data-testid="stThumbValue"],
    .stSlider [role="slider"] div {{
        color: #000 !important;
    }}
    </style>""",
    unsafe_allow_html=True,
)

# Save only when the user actually changes the rating (avoids redundant DB writes)
if new_rating != current_rating:
    st.session_state.ratings[movie["id"]] = new_rating  # Update runtime state
    save_rating(movie["id"], new_rating)  # Persist to SQLite

# --- Action buttons ---
# Watchlist and dismiss are separate actions that advance to the next movie.


def _add_to_watchlist() -> None:
    """Add current movie to watchlist and advance to next."""
    st.session_state.watchlist.append(movie)  # Update runtime state
    save_to_watchlist(movie)  # Persist full movie dict to SQLite
    st.session_state.discover_index += 1  # Advance to next movie on rerun


def _dismiss() -> None:
    """Mark current movie as dismissed and advance to next."""
    st.session_state.dismissed.add(movie["id"])  # Update runtime set
    save_dismissed(movie["id"])  # Persist dismissal to SQLite
    st.session_state.discover_index += 1  # Advance to next movie on rerun


with st.container(horizontal=True):
    st.button("Not interested", icon=":material/thumb_down:", on_click=_dismiss)
    st.button(
        "Add to watchlist", icon=":material/bookmark:",
        on_click=_add_to_watchlist, type="primary",
    )

