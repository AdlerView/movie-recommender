"""Rate page — Search and rate movies you've already seen.

Find movies via TMDB text search or browse trending titles, then rate them
on a 0.00-10.00 scale matching the TMDB rating system. Clicking a poster
opens a detail dialog with rating slider. Pure action tab — rated movies
are reviewed on the Statistics page instead.
"""
from __future__ import annotations

import requests
import streamlit as st
from utils.db import save_movie_details, save_rating
from utils.tmdb import (
    get_movie_details,
    get_trending,
    poster_url,
    search_movies,
)

st.header("Rate a movie", divider="gray")

# --- Deferred toast ---
# Shown after rerun following a save (st.toast before st.rerun is lost)
if "_watched_toast" in st.session_state:
    st.toast(st.session_state.pop("_watched_toast"), icon=":material/star:")

# --- State management ---
# _watched_selected_id: movie ID to show in the detail dialog (int or None)
st.session_state.setdefault("_watched_selected_id", None)
# Pagination: how many TMDB pages are loaded (20 movies per page)
st.session_state.setdefault("_watched_pages", 1)
# Track previous query to reset pagination when the search term changes
st.session_state.setdefault("_watched_prev_query", "")

# Number of columns in the poster grid
_GRID_COLS = 5
# TMDB returns 20 results per page — used to detect when no more pages exist
_TMDB_PAGE_SIZE = 20


def _select_movie_id(movie_id: int) -> None:
    """Set the selected movie ID to trigger the detail dialog.

    Args:
        movie_id: TMDB movie ID to show details for.
    """
    st.session_state._watched_selected_id = movie_id


def _load_more() -> None:
    """Load the next page of trending/search results."""
    st.session_state._watched_pages += 1



# --- Dialog: movie detail + rating overlay ---
@st.dialog("Rate movie", width="large")
def _show_rating_dialog(movie_id: int) -> None:
    """Render movie detail dialog with rating slider.

    Args:
        movie_id: TMDB movie ID to display and rate.
    """
    # Fetch full details (cached 1h) for runtime, genres, overview
    try:
        details = get_movie_details(movie_id)
    except requests.RequestException:
        st.error("Could not load movie details.", icon=":material/error:")
        return

    # --- Movie info card ---
    col_poster, col_info = st.columns([1, 2])
    with col_poster:
        st.image(poster_url(details.get("poster_path"), size="w500"), width=250)
    with col_info:
        st.subheader(details.get("title", "Unknown"))
        # Genre badges
        genres = details.get("genres", [])
        if genres:
            st.markdown(" ".join(f":gray-badge[{g['name']}]" for g in genres))
        # TMDB rating
        st.caption(f"TMDB rating: {details.get('vote_average', 'N/A')} / 10")
        # Runtime
        runtime = details.get("runtime")
        if runtime:
            hours, mins = divmod(runtime, 60)
            if hours:
                st.caption(f":material/schedule: {hours}h {mins}min")
            else:
                st.caption(f":material/schedule: {mins} min")
        # Overview
        st.write(details.get("overview", "No description available."))

    st.divider()

    # --- Rating slider ---
    # Pre-fill with existing rating if the movie was previously rated
    current_rating = st.session_state.ratings.get(movie_id)
    new_rating = st.slider(
        "Your rating",
        min_value=0.00,
        max_value=10.00,
        value=current_rating if current_rating is not None else 0.00,
        step=0.01,
        format="%.2f/10",
        key=f"watched_rate_{movie_id}",
    )

    # Dynamic slider color: gray (0), red (<=3.33), orange (<=6.66), green (>6.66)
    if new_rating == 0.00:
        _color = "#d3d3d3"
    elif new_rating <= 3.33:
        _color = "#ff4b4b"
    elif new_rating <= 6.66:
        _color = "#ffa421"
    else:
        _color = "#21c354"
    st.markdown(
        f"""<style>
        .stSlider > div > div > div > div {{
            background: {_color} !important;
        }}
        .stSlider [role="slider"] {{
            background-color: #000 !important;
            border-color: #000 !important;
        }}
        .stSlider [role="slider"]:focus,
        .stSlider [role="slider"]:active {{
            box-shadow: 0 0 0 0.2rem rgba(0, 0, 0, 0.2) !important;
            outline: none !important;
        }}
        .stSlider [data-testid="stThumbValue"],
        .stSlider [role="slider"] div {{
            color: #000 !important;
        }}
        </style>""",
        unsafe_allow_html=True,
    )

    # Save button — persists rating and closes dialog
    if st.button("Save rating", type="primary", icon=":material/save:"):
        st.session_state.ratings[movie_id] = new_rating
        save_rating(movie_id, new_rating)
        # Eager fetch: cache full TMDB details for Statistics dashboard
        try:
            save_movie_details(movie_id, details)
        except Exception:
            pass
        st.session_state._watched_selected_id = None
        st.session_state["_watched_toast"] = (
            f"Rated **{details.get('title', '')}**: {new_rating:.2f}/10"
        )
        st.rerun()


# === Search & Browse ===
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
# Loads pages until we have enough unrated movies to fill the grid.
# Rated movies are excluded (they appear in "Your ratings" below),
# so we may need extra pages to compensate for filtered-out entries.
rated_ids = st.session_state.get("ratings", {})
target_count = st.session_state._watched_pages * _TMDB_PAGE_SIZE
movies: list[dict] = []
has_more = True  # Whether more pages are available from TMDB
_max_pages = 10  # Safety cap to avoid excessive API calls

try:
    p = 0
    while len(movies) < target_count and has_more and p < _max_pages:
        p += 1
        if current_query:
            page_movies = search_movies(current_query, page=p)
        else:
            page_movies = get_trending(page=p)
        if not page_movies:
            has_more = False
            break
        # Filter per page: remove poster-less, already-rated, and duplicate movies
        seen_ids = {m["id"] for m in movies}
        page_movies = [
            m for m in page_movies
            if m.get("poster_path") and m["id"] not in rated_ids
            and m["id"] not in seen_ids
        ]
        movies.extend(page_movies)
        # TMDB returns 20 per page; fewer means we've reached the last page
        if len(page_movies) < _TMDB_PAGE_SIZE:
            has_more = p < _max_pages
    # Trim to exact target count
    movies = movies[:target_count]
except requests.HTTPError:
    st.error("TMDB API error. Please try again later.", icon=":material/error:")
    st.stop()
except requests.ConnectionError:
    st.error(
        "Could not connect to TMDB. Check your internet connection.",
        icon=":material/wifi_off:",
    )
    st.stop()

if not movies:
    st.info(
        "No movies found. Try a different search term.",
        icon=":material/search_off:",
    )
    st.stop()

# --- Poster grid (Netflix-style: clickable poster images) ---
# CSS overlays a transparent button on each poster for click interaction.
# Scoped to .st-key-poster_grid to avoid affecting other columns on the page.
st.markdown("""<style>
    .st-key-poster_grid [data-testid="stColumn"] {
        position: relative !important;
        cursor: pointer !important;
    }
    .st-key-poster_grid [data-testid="stColumn"] [data-testid="stElementContainer"]:has(.stButton) {
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        width: 100% !important;
        height: 100% !important;
        z-index: 10 !important;
    }
    .st-key-poster_grid [data-testid="stElementContainer"]:has(.stButton) .stButton,
    .st-key-poster_grid [data-testid="stElementContainer"]:has(.stButton) .stButton button {
        width: 100% !important;
        height: 100% !important;
        max-width: 100% !important;
        opacity: 0 !important;
        cursor: pointer !important;
        border: none !important;
        background: transparent !important;
        padding: 0 !important;
    }
    .st-key-poster_grid [data-testid="stColumn"]:hover {
        opacity: 0.85;
        transition: opacity 0.2s;
    }
</style>""", unsafe_allow_html=True)

with st.container(key="poster_grid"):
    for row_start in range(0, len(movies), _GRID_COLS):
        row_movies = movies[row_start:row_start + _GRID_COLS]
        cols = st.columns(_GRID_COLS)
        for col, movie in zip(cols, row_movies):
            with col:
                # Poster image (w342 for sharp display in 5-column grid)
                st.image(poster_url(movie.get("poster_path"), size="w342"))
                # Invisible button overlay — captures clicks on the poster
                st.button(
                    "Rate",
                    key=f"watched_sel_{movie['id']}",
                    on_click=_select_movie_id,
                    args=(movie["id"],),
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

# --- Trigger dialog after page renders (dialog must be called in main flow) ---
if st.session_state._watched_selected_id is not None:
    _show_rating_dialog(st.session_state._watched_selected_id)
