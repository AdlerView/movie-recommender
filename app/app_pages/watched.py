"""Watched page — Search, rate, and re-rate movies you've already seen.

Find movies via TMDB text search or browse trending titles, then rate them
on a 0.00-10.00 scale matching the TMDB rating system. Below the trending
section, all previously rated movies are listed with re-rating sliders.
Ratings persist to session state (runtime) and SQLite (disk).
"""
from __future__ import annotations

import requests
import streamlit as st
from utils.db import save_rating
from utils.tmdb import (
    get_genre_map,
    get_movie_details,
    get_trending,
    poster_url,
    search_movies,
)

st.header("Rate a movie", divider="blue")

# --- Deferred toast ---
# Shown after rerun following a save (st.toast before st.rerun is lost)
if "_watched_toast" in st.session_state:
    st.toast(st.session_state.pop("_watched_toast"), icon=":material/star:")

# --- Load genre data for badge display on movie cards ---
try:
    genre_map = get_genre_map()
except requests.HTTPError:
    st.error("TMDB API error. Please try again later.", icon=":material/error:")
    st.stop()
except requests.ConnectionError:
    st.error(
        "Could not connect to TMDB. Check your internet connection.",
        icon=":material/wifi_off:",
    )
    st.stop()

# --- State management ---
# watched_selected: the movie currently being rated (dict or None)
st.session_state.setdefault("watched_selected", None)
# Pagination: how many TMDB pages are loaded (20 movies per page)
st.session_state.setdefault("_watched_pages", 1)
# Track previous query to reset pagination when the search term changes
st.session_state.setdefault("_watched_prev_query", "")

# Number of columns in the poster grid
_GRID_COLS = 5
# TMDB returns 20 results per page — used to detect when no more pages exist
_TMDB_PAGE_SIZE = 20
# Number of rated movies shown initially and per "Load more" click
_RATED_PAGE_SIZE = 5
st.session_state.setdefault("_rated_show_count", _RATED_PAGE_SIZE)


def _select_movie(movie: dict) -> None:
    """Select a movie from the grid for rating.

    Args:
        movie: TMDB movie dict to rate.
    """
    st.session_state.watched_selected = movie


def _back_to_search() -> None:
    """Return to search/browse view, clearing the selected movie."""
    st.session_state.watched_selected = None


def _load_more() -> None:
    """Load the next page of trending/search results."""
    st.session_state._watched_pages += 1


def _load_more_rated() -> None:
    """Show more rated movies in the Your Ratings section."""
    st.session_state._rated_show_count += _RATED_PAGE_SIZE


# === PHASE 1: Search & Browse ===
if st.session_state.watched_selected is None:
    # Search field — results update on Enter/blur (Streamlit default behavior)
    query = st.text_input(
        "Search for a movie you've watched",
        placeholder="e.g. Inception, The Matrix, Parasite...",
        key="watched_search",
        icon=":material/search:",
    )

    # Normalize query for comparison and pagination reset
    current_query = query.strip() if query else ""

    # Reset pagination when the search term changes
    if current_query != st.session_state._watched_prev_query:
        st.session_state._watched_pages = 1
        st.session_state._watched_prev_query = current_query

    if not current_query:
        # No search query — show trending movies as quick entry point
        st.subheader("Trending movies")
        st.caption("Movies you might have already seen")

    # --- Fetch movies with pagination ---
    # Loads pages 1 through _watched_pages; each page is individually cached.
    movies: list[dict] = []
    has_more = True  # Whether more pages are available from TMDB

    try:
        for p in range(1, st.session_state._watched_pages + 1):
            if current_query:
                page_movies = search_movies(current_query, page=p)
            else:
                page_movies = get_trending(page=p)
            if not page_movies:
                has_more = False
                break
            movies.extend(page_movies)
            # TMDB returns 20 per page; fewer means we've reached the last page
            if len(page_movies) < _TMDB_PAGE_SIZE:
                has_more = False
                break
    except requests.HTTPError:
        st.error("TMDB API error. Please try again later.", icon=":material/error:")
        st.stop()
    except requests.ConnectionError:
        st.error(
            "Could not connect to TMDB. Check your internet connection.",
            icon=":material/wifi_off:",
        )
        st.stop()

    # Filter out movies without poster artwork (keeps the grid visually consistent)
    movies = [m for m in movies if m.get("poster_path")]

    if not movies:
        st.info(
            "No movies found. Try a different search term.",
            icon=":material/search_off:",
        )
        st.stop()

    # --- Poster grid (Netflix-style: clickable poster images) ---
    # CSS overlays a transparent button on each poster for click interaction.
    # No JavaScript needed — pure CSS positioning makes the button cover the poster.
    st.markdown("""<style>
        /* Enable absolute positioning within grid columns */
        [data-testid="column"] {
            position: relative !important;
        }
        /* Overlay button container over the entire column area */
        [data-testid="column"] .stButton {
            position: absolute !important;
            top: 0 !important;
            left: 0 !important;
            right: 0 !important;
            bottom: 0 !important;
            z-index: 10 !important;
        }
        /* Transparent full-size button — invisible but captures clicks */
        [data-testid="column"] .stButton button {
            width: 100% !important;
            height: 100% !important;
            opacity: 0 !important;
            cursor: pointer !important;
            border: none !important;
        }
        /* Hover: slight dim on poster columns only (those with a button overlay) */
        [data-testid="column"]:has(.stButton):hover {
            opacity: 0.85;
            transition: opacity 0.2s;
        }
    </style>""", unsafe_allow_html=True)

    for row_start in range(0, len(movies), _GRID_COLS):
        row_movies = movies[row_start:row_start + _GRID_COLS]
        cols = st.columns(_GRID_COLS)
        for col, movie in zip(cols, row_movies):
            with col:
                # Poster image (w342 for sharp display in 5-column grid)
                st.image(poster_url(movie.get("poster_path"), size="w342"))
                # Transparent button overlay — covers the poster for click target
                st.button(
                    movie["title"],
                    key=f"watched_sel_{movie['id']}",
                    on_click=_select_movie,
                    args=(movie,),
                )

    # --- Load more button ---
    # Shown when TMDB has more pages of results available
    if has_more:
        st.button(
            "Load more",
            icon=":material/expand_more:",
            on_click=_load_more,
            use_container_width=True,
        )

    # --- Your ratings section (below trending, hidden during search) ---
    # Shows all previously rated movies with re-rating sliders.
    # Only visible when browsing (no search query) and at least one rating exists.
    ratings = st.session_state.get("ratings", {})
    if not current_query and ratings:
        st.subheader("Your ratings", divider="blue")

        # Build lookup: watchlist movies have metadata cached in session state.
        # Rated movies NOT in the watchlist need a TMDB API call for title/poster.
        watchlist_lookup: dict[int, dict] = {
            m["id"]: m for m in st.session_state.get("watchlist", [])
        }

        # Paginate: show first _rated_show_count entries
        rated_items = list(ratings.items())
        visible_items = rated_items[:st.session_state._rated_show_count]

        # Fetch metadata for visible rated movies not in the watchlist (cached 1h)
        for movie_id, _ in visible_items:
            if movie_id not in watchlist_lookup:
                try:
                    # GET /movie/{id} — retrieves title, poster, rating for display
                    watchlist_lookup[movie_id] = get_movie_details(movie_id)
                except requests.RequestException:
                    # Graceful fallback — show movie ID if API call fails
                    watchlist_lookup[movie_id] = {
                        "id": movie_id, "title": f"Movie #{movie_id}",
                    }

        # Render rated movie cards with re-rating sliders
        for movie_id, current_rating in visible_items:
            rated_movie = watchlist_lookup[movie_id]

            with st.container(border=True):
                # 2-column layout: compact poster, wide info area
                col_poster, col_info = st.columns([1, 3])
                with col_poster:
                    st.image(
                        poster_url(rated_movie.get("poster_path"), size="w185"),
                        width=100,
                    )
                with col_info:
                    st.subheader(
                        rated_movie.get("title", f"Movie #{movie_id}")
                    )
                    st.caption(
                        f"TMDB rating: "
                        f"{rated_movie.get('vote_average', 'N/A')} / 10"
                    )

                # Re-rating slider — auto-saves on change (same scale: 0.00-10.00)
                new_rating = st.slider(
                    "Your rating",
                    min_value=0.00,
                    max_value=10.00,
                    value=current_rating if current_rating is not None else 0.00,
                    step=0.01,
                    format="%.2f/10",
                    key=f"rated_{movie_id}",
                )
                # Save only when the rating actually changes (avoids redundant writes)
                if new_rating != current_rating:
                    st.session_state.ratings[movie_id] = new_rating
                    save_rating(movie_id, new_rating)

        # Load more rated movies
        if len(rated_items) > st.session_state._rated_show_count:
            st.button(
                "Load more",
                icon=":material/expand_more:",
                on_click=_load_more_rated,
                use_container_width=True,
                key="load_more_rated",
            )

        # Footer: total count
        st.caption(
            f"{len(ratings)} movie{'s' if len(ratings) != 1 else ''} rated"
        )

    st.stop()  # Halt rendering — Phase 1 content only

# === PHASE 2: Rate Selected Movie ===
movie = st.session_state.watched_selected

# Back button to return to search/browse
st.button("Back to search", icon=":material/arrow_back:", on_click=_back_to_search)

# Resolve genre IDs to human-readable names for badge display
genre_names = [genre_map.get(gid, "Unknown") for gid in movie.get("genre_ids", [])]

# --- Movie card (same layout as Discover page) ---
with st.container(border=True):
    col_poster, col_info = st.columns([1, 2])
    with col_poster:
        # w342 poster size for detail card display
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
# Shows existing rating if the movie was previously rated.
current_rating = st.session_state.ratings.get(movie["id"])

new_rating = st.slider(
    "Your rating",
    min_value=0.00,
    max_value=10.00,
    value=current_rating if current_rating is not None else 0.00,
    step=0.01,
    format="%.2f/10",
    key=f"watched_rate_{movie['id']}",
)

# Dynamic slider color: gray (0), red (<=3.33), orange (<=6.66), green (>6.66)
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

# Save button — persists rating and returns to search/browse view
if st.button("Save rating", type="primary", icon=":material/save:"):
    st.session_state.ratings[movie["id"]] = new_rating  # Update runtime state
    save_rating(movie["id"], new_rating)  # Persist to SQLite
    # Store toast message for display after rerun (toast before rerun is lost)
    st.session_state["_watched_toast"] = f"Rated **{movie['title']}**: {new_rating:.2f}/10"
    st.session_state.watched_selected = None  # Return to search/browse phase
    st.rerun()  # Immediate transition back to the grid
