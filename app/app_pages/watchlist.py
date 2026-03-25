"""Watchlist page — Poster grid of saved movies with detail dialog.

Displays movies the user has added from the Discover page as a Netflix-style
poster grid. Clicking a poster opens a dialog with TMDB rating, streaming
providers, and actions (remove from watchlist, mark as watched with rating).
"""
from __future__ import annotations

import requests
import streamlit as st
from utils.db import (
    remove_from_watchlist,
    save_movie_details,
    save_movie_keywords,
    save_rating,
)
from utils.tmdb import get_movie_details, get_movie_keywords, poster_url

# Provider brand colors for badge styling
_PROVIDER_COLORS: dict[str, str] = {
    "Netflix": "red",
    "Amazon Prime Video": "blue",
    "Disney Plus": "green",
    "Apple TV Plus": "gray",
    "Paramount Plus": "orange",
}
_DEFAULT_PROVIDER_COLOR = "violet"

# Number of columns in the poster grid (matches Watched page)
_GRID_COLS = 5

st.header("Your watchlist", divider="gray", text_alignment="center")

# --- Deferred toast ---
if "_watchlist_toast" in st.session_state:
    st.toast(st.session_state.pop("_watchlist_toast"), icon=":material/bookmark:")

# --- State management ---
st.session_state.setdefault("_watchlist_selected", None)

# Read shared state — loaded from SQLite on app start, updated on every action
watchlist: list[dict] = st.session_state.get("watchlist", [])

# --- Empty state ---
if not watchlist:
    st.info(
        "No movies in your watchlist yet. Head to Discover to find some!",
        icon=":material/bookmark_border:",
    )
    st.stop()


def _select_movie(movie_id: int) -> None:
    """Set the selected movie ID to trigger the detail dialog.

    Args:
        movie_id: TMDB movie ID to show details for.
    """
    st.session_state._watchlist_selected = movie_id


# --- Dialog: movie detail overlay ---
@st.dialog("Movie details", width="large")
def _show_detail(movie_id: int) -> None:
    """Render movie detail dialog with streaming info and actions.

    Args:
        movie_id: TMDB movie ID to display.
    """
    # Fetch full details (cached 1h) for runtime, genres, providers, overview
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
        # Genre section
        genres = details.get("genres", [])
        if genres:
            st.caption("**Genre**")
            st.markdown(" ".join(
                f":gray-badge[{g['name']}]" for g in genres
            ))
        # TMDB rating — 1 decimal for consistent display
        _tmdb = details.get("vote_average")
        st.caption(f"TMDB rating: {_tmdb:.1f} / 10" if _tmdb else "TMDB rating: N/A")
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

    # --- Streaming providers (Switzerland) ---
    providers_data = details.get("watch/providers", {}).get("results", {}).get("CH", {})
    flatrate = providers_data.get("flatrate", [])
    if flatrate:
        st.markdown("**Streaming in Switzerland:** " + " ".join(
            f":{_PROVIDER_COLORS.get(p['provider_name'], _DEFAULT_PROVIDER_COLOR)}-badge[{p['provider_name']}]"
            for p in flatrate
        ))

    st.divider()

    # --- Actions ---
    col_remove, col_watched = st.columns(2)
    with col_remove:
        if st.button(
            "Remove from watchlist",
            icon=":material/delete:",
            use_container_width=True,
        ):
            # Remove from session state and database
            st.session_state.watchlist = [
                m for m in st.session_state.watchlist if m["id"] != movie_id
            ]
            remove_from_watchlist(movie_id)
            st.session_state._watchlist_selected = None
            st.session_state["_watchlist_toast"] = f"Removed **{details.get('title', '')}** from watchlist"
            st.rerun()

    with col_watched:
        if st.button(
            "Mark as watched",
            icon=":material/visibility:",
            type="primary",
            use_container_width=True,
        ):
            # Switch to rating mode inside the dialog
            st.session_state["_watchlist_show_rating"] = True

    # --- Rating slider (shown after "Mark as watched" click) ---
    if st.session_state.get("_watchlist_show_rating"):
        st.subheader("Rate this movie")
        # Track whether slider was moved — prevents accidental 0-ratings
        _touch_key = f"_wl_touched_{movie_id}"
        st.session_state.setdefault(_touch_key, False)

        def _mark_touched() -> None:
            st.session_state[_touch_key] = True

        new_rating = st.slider(
            "Your rating",
            min_value=0.00,
            max_value=10.00,
            value=0.00,
            step=0.01,
            format="%.2f/10",
            key=f"watchlist_rate_{movie_id}",
            on_change=_mark_touched,
        )

        # Dynamic sentiment label — changes with slider value
        if new_rating == 0.00:
            _label = ""
        elif new_rating <= 2.00:
            _label = "Awful"
        elif new_rating <= 4.00:
            _label = "Poor"
        elif new_rating <= 6.00:
            _label = "Decent"
        elif new_rating <= 8.00:
            _label = "Great"
        else:
            _label = "Masterpiece"
        if _label:
            st.caption(_label, text_alignment="center")

        # Dynamic slider color: gray (0), red (<=3.33), orange (<=6.66), green (>6.66)
        if new_rating == 0.00:
            _color = "#d3d3d3"
        elif new_rating <= 3.33:
            _color = "#ff4b4b"
        elif new_rating <= 6.66:
            _color = "#ffa421"
        else:
            _color = "#21c354"
        # Generate CSS dot positions at every 10% (0%, 10%, ... 100%)
        _dots = ", ".join(
            f"radial-gradient(circle, rgba(255,255,255,0.6) 3px, transparent 3px) {i*10}% 50%"
            for i in range(11)
        )
        st.markdown(
            f"""<style>
            .stSlider > div > div > div > div {{
                background: {_color} !important;
            }}
            /* Hide tick dot decorations below slider, keep min/max value labels */
            .stSlider [data-testid="stSliderTickBar"] {{
                background: none !important;
                background-image: none !important;
            }}
            .stSlider [data-testid="stSliderTickBar"]::before,
            .stSlider [data-testid="stSliderTickBar"]::after {{
                display: none !important;
            }}
            /* Dot tick marks at whole numbers on the slider track */
            .stSlider [data-baseweb="slider"] > div {{
                position: relative !important;
            }}
            .stSlider [data-baseweb="slider"] > div::after {{
                content: '' !important;
                position: absolute !important;
                left: 0 !important;
                right: 0 !important;
                top: 50% !important;
                height: 7px !important;
                transform: translateY(-50%) !important;
                background: {_dots} !important;
                background-repeat: no-repeat !important;
                background-size: 7px 7px !important;
                pointer-events: none !important;
                z-index: 1 !important;
            }}
            .stSlider [role="slider"] {{
                background-color: #000 !important;
                border-color: #000 !important;
                z-index: 2 !important;
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

        # Save button — disabled until the slider is moved at least once
        _slider_ready = st.session_state.get(_touch_key, False)
        if not _slider_ready:
            st.caption("Move the slider to set your rating", text_alignment="center")
        if st.button("Save rating", type="primary", icon=":material/save:", disabled=not _slider_ready):
            # Save rating to session state and database
            st.session_state.ratings[movie_id] = new_rating
            save_rating(movie_id, new_rating)
            # Eager fetch: cache full TMDB details + keywords for Statistics/ML
            try:
                save_movie_details(movie_id, details)
            except Exception:
                pass
            try:
                save_movie_keywords(movie_id, get_movie_keywords(movie_id))
            except Exception:
                pass
            # Remove from watchlist (watched = no longer on watchlist)
            st.session_state.watchlist = [
                m for m in st.session_state.watchlist if m["id"] != movie_id
            ]
            remove_from_watchlist(movie_id)
            # Clean up dialog state
            st.session_state._watchlist_selected = None
            st.session_state.pop("_watchlist_show_rating", None)
            st.session_state.pop(_touch_key, None)
            st.session_state["_watchlist_toast"] = (
                f"Rated **{details.get('title', '')}**: {new_rating:.2f}/10"
            )
            st.rerun()


# --- Clickable poster grid CSS (same pattern as Watched page) ---
# Scoped to .st-key-watchlist_grid to avoid affecting other elements.
st.markdown("""<style>
    .st-key-watchlist_grid [data-testid="stColumn"] {
        position: relative !important;
        cursor: pointer !important;
    }
    .st-key-watchlist_grid [data-testid="stColumn"] [data-testid="stElementContainer"]:has(.stButton) {
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        width: 100% !important;
        height: 100% !important;
        z-index: 10 !important;
    }
    .st-key-watchlist_grid [data-testid="stElementContainer"]:has(.stButton) .stButton,
    .st-key-watchlist_grid [data-testid="stElementContainer"]:has(.stButton) .stButton button {
        width: 100% !important;
        height: 100% !important;
        max-width: 100% !important;
        opacity: 0 !important;
        cursor: pointer !important;
        border: none !important;
        background: transparent !important;
        padding: 0 !important;
    }
    .st-key-watchlist_grid [data-testid="stColumn"]:hover {
        opacity: 0.85;
        transition: opacity 0.2s;
    }
</style>""", unsafe_allow_html=True)

# --- Poster grid ---
# Filter out movies without posters for visual consistency
grid_movies = [m for m in watchlist if m.get("poster_path")]

with st.container(key="watchlist_grid"):
    for row_start in range(0, len(grid_movies), _GRID_COLS):
        row_movies = grid_movies[row_start:row_start + _GRID_COLS]
        cols = st.columns(_GRID_COLS)
        for col, movie in zip(cols, row_movies):
            with col:
                st.image(poster_url(movie.get("poster_path"), size="w342"))
                # Invisible button overlay — captures clicks on the poster
                st.button(
                    "Details",
                    key=f"wl_sel_{movie['id']}",
                    on_click=_select_movie,
                    args=(movie["id"],),
                )

# Footer: total count
st.caption(
    f"{len(watchlist)} movie{'s' if len(watchlist) != 1 else ''} in your watchlist"
)

# --- Trigger dialog after grid renders (dialog must be called in main flow) ---
if st.session_state._watchlist_selected is not None:
    _show_detail(st.session_state._watchlist_selected)
