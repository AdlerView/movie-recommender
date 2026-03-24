"""Discover page — Browse and discover new movies by genre, mood, and keywords.

Two-phase flow: first select genre tags, mood tags, and optional keyword tags,
then browse filtered movies one at a time in a card-based flow. Genres are hard
AND filters (via TMDB API), moods and keywords are soft relevance ranking (via
local keywords.db). Add to watchlist or dismiss. Rating happens on the Rate page.
"""
from __future__ import annotations

import requests
import streamlit as st
from utils.db import (
    MOOD_KEYWORD_NAMES,
    get_movie_keywords_from_index,
    get_popular_keywords,
    keywords_db_available,
    save_dismissed,
    save_to_watchlist,
    score_movies_by_keywords,
)
from utils.tmdb import discover_movies, get_genre_map, get_trending, poster_url

# Header changes based on phase: genre selection vs. movie browsing
if st.session_state.get("discover_phase", "select") == "select":
    st.header("Which movie will you watch?", divider="gray", text_alignment="center")
else:
    st.header("Discover movies", divider="gray")

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

# --- Load keyword + mood data for tag selection ---
# Keywords come from the pre-populated keywords.db (read-only, no API calls).
# Build name→id lookups so we can resolve pill selections to keyword IDs.
_keyword_name_to_id: dict[str, int] = {}
_keyword_options: list[str] = []
_mood_name_to_id: dict[str, int] = {}
_mood_options: list[str] = []
if keywords_db_available():
    _popular_keywords = get_popular_keywords(limit=30)
    _keyword_name_to_id = {kw["keyword_name"]: kw["keyword_id"] for kw in _popular_keywords}
    _keyword_options = [kw["keyword_name"] for kw in _popular_keywords]
    # Resolve mood names against keywords.db — only show moods that exist in the index
    _all_kw_by_name = {kw["keyword_name"]: kw["keyword_id"] for kw in get_popular_keywords(limit=500)}
    for mood in MOOD_KEYWORD_NAMES:
        if mood in _all_kw_by_name:
            _mood_name_to_id[mood] = _all_kw_by_name[mood]
            _mood_options.append(mood)

# --- Phase management ---
# Two phases: "select" (genre + keyword tags) → "browse" (movie cards)
st.session_state.setdefault("discover_phase", "select")
st.session_state.setdefault("discover_index", 0)


def _start_browsing() -> None:
    """Transition from genre/mood/keyword selection to movie browsing."""
    # Read current genre pill selection from widget state
    selected = st.session_state.get("genre_pills", [])
    # Reverse-lookup: resolve genre names back to TMDB genre IDs for the API call
    st.session_state["_discover_genres"] = tuple(sorted(
        gid for gid, name in genre_map.items() if name in (selected or [])
    ))
    # Collect keyword IDs from both mood and keyword pills for unified scoring
    all_keyword_ids: list[int] = []
    # Mood pills → keyword IDs
    selected_mood_names = st.session_state.get("mood_pills", [])
    if selected_mood_names and _mood_name_to_id:
        all_keyword_ids.extend(
            _mood_name_to_id[name]
            for name in selected_mood_names
            if name in _mood_name_to_id
        )
    # Keyword pills → keyword IDs
    selected_kw_names = st.session_state.get("keyword_pills", [])
    if selected_kw_names and _keyword_name_to_id:
        all_keyword_ids.extend(
            _keyword_name_to_id[name]
            for name in selected_kw_names
            if name in _keyword_name_to_id
        )
    st.session_state["_discover_keywords"] = tuple(all_keyword_ids)
    # Switch to browse phase and reset movie position to the first result
    st.session_state.discover_phase = "browse"
    st.session_state.discover_index = 0


def _back_to_selection() -> None:
    """Return to genre/keyword selection phase."""
    st.session_state.discover_phase = "select"


# === PHASE 1: Genre + Keyword Selection ===
if st.session_state.discover_phase == "select":
    # Genre pills — hard AND filter via TMDB API
    st.subheader("Genre")
    selected_genres = st.pills(
        "Genre",
        options=list(genre_map.values()),
        selection_mode="multi",
        key="genre_pills",
        label_visibility="collapsed",
    )

    # Mood pills — soft relevance ranking, same scoring as keywords
    selected_moods: list[str] = []
    if _mood_options:
        st.subheader("Mood")
        selected_moods = st.pills(
            "Mood",
            options=_mood_options,
            selection_mode="multi",
            key="mood_pills",
            label_visibility="collapsed",
        )

    # Keyword pills — soft relevance ranking via keywords.db (only shown if DB exists)
    selected_keywords: list[str] = []
    if _keyword_options:
        st.subheader("Keywords")
        selected_keywords = st.pills(
            "Keywords",
            options=_keyword_options,
            selection_mode="multi",
            key="keyword_pills",
            label_visibility="collapsed",
        )

    # Button label adapts: "Search" with any selection, "Show trending" without
    has_selection = selected_genres or selected_moods or selected_keywords
    st.button(
        "Search" if has_selection else "Show trending",
        icon=":material/search:",
        on_click=_start_browsing,
        type="primary",
    )
    st.stop()  # Halt rendering — only selection UI is shown in this phase

# === PHASE 2: Movie Browsing ===
# Retrieve genre IDs and keyword IDs stored by _start_browsing callback
selected_ids = st.session_state.get("_discover_genres", ())
selected_keyword_ids = st.session_state.get("_discover_keywords", ())

# Back button to return to genre/keyword selection
st.button("Change filters", icon=":material/arrow_back:", on_click=_back_to_selection)

# --- Load movies with automatic pagination ---
# When keywords are active, pre-fetch more pages to build a ranking pool.
# Without keywords, stop as soon as any available movie is found.
dismissed = st.session_state.dismissed
watchlisted_ids = {m["id"] for m in st.session_state.watchlist}
rated_ids = st.session_state.ratings  # dict {movie_id: rating} — membership check is O(1)
available: list[dict] = []  # Accumulates unseen movies across pages
# 5 pages (~100 movies) gives enough pool for meaningful keyword ranking
_TARGET_POOL = 100 if selected_keyword_ids else 1

try:
    for page in range(1, 11):
        if selected_ids:
            movies = discover_movies(selected_ids, page=page)
        else:
            movies = get_trending(page=page)

        if not movies:
            break  # No more results from API

        # Filter out dismissed, watchlisted, and already-rated movies
        available.extend(
            m for m in movies
            if m["id"] not in dismissed
            and m["id"] not in watchlisted_ids
            and m["id"] not in rated_ids
        )

        # Without keywords: stop at first available movie
        # With keywords: collect enough movies for ranking
        if available and len(available) >= _TARGET_POOL:
            break
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

# --- Keyword scoring ---
# Score movies by how many selected keywords they match, then sort by
# score (descending) with TMDB popularity as tiebreaker. Movies not in
# the keyword index get score 0 and appear after all scored movies.
if selected_keyword_ids and available:
    scores = score_movies_by_keywords(
        [m["id"] for m in available],
        list(selected_keyword_ids),
    )
    available.sort(key=lambda m: (-scores.get(m["id"], 0), -m.get("popularity", 0)))

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

# Look up all keywords from the keyword index (no API call, always shown)
movie_keywords = get_movie_keywords_from_index(movie["id"])
# Split into mood and regular keywords for separate display sections
mood_kws = [kw for kw in movie_keywords if kw["keyword_name"] in MOOD_KEYWORD_NAMES]
regular_kws = [kw for kw in movie_keywords if kw["keyword_name"] not in MOOD_KEYWORD_NAMES]

# Card layout: poster on the left, info on the right
with st.container(border=True):
    col_poster, col_info = st.columns([1, 2])
    with col_poster:
        # w342 poster size for card display
        st.image(poster_url(movie.get("poster_path")), width=250)
    with col_info:
        st.subheader(movie["title"])
        # Genre section
        if genre_names:
            st.caption("**Genre**")
            st.markdown(" ".join(f":gray-badge[{g}]" for g in genre_names))
        # Mood section — always primary (Cinema Gold)
        if mood_kws:
            st.caption("**Mood**")
            st.markdown(" ".join(
                f":primary-badge[{kw['keyword_name']}]" for kw in mood_kws
            ))
        # Keywords section — always gray
        if regular_kws:
            st.caption("**Keywords**")
            st.markdown(" ".join(
                f":gray-badge[{kw['keyword_name']}]" for kw in regular_kws
            ))
        st.caption(f"TMDB rating: {movie.get('vote_average', 'N/A')} / 10")
        st.write(movie.get("overview", "No description available."))

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

