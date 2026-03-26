"""Utility modules for the movie recommender app.

Shared UI helpers used across multiple pages to avoid code duplication.
"""
from __future__ import annotations

import streamlit as st


def inject_poster_grid_css(container_key: str) -> None:
    """Inject CSS for a clickable poster grid with invisible button overlays.

    Scoped to the given container key to avoid affecting other elements.
    Uses st.html() so the style block doesn't take up layout space.

    Args:
        container_key: The key passed to st.container() wrapping the grid.
    """
    st.html(f"""<style>
        .st-key-{container_key} [data-testid="stColumn"] {{
            position: relative !important;
            cursor: pointer !important;
        }}
        .st-key-{container_key} [data-testid="stColumn"] [data-testid="stElementContainer"]:has(.stButton) {{
            position: absolute !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 100% !important;
            z-index: 10 !important;
        }}
        .st-key-{container_key} [data-testid="stElementContainer"]:has(.stButton) .stButton,
        .st-key-{container_key} [data-testid="stElementContainer"]:has(.stButton) .stButton button {{
            width: 100% !important;
            height: 100% !important;
            max-width: 100% !important;
            opacity: 0 !important;
            cursor: pointer !important;
            border: none !important;
            background: transparent !important;
            padding: 0 !important;
        }}
        .st-key-{container_key} [data-testid="stColumn"]:hover {{
            opacity: 0.85;
            transition: opacity 0.2s;
        }}
    </style>""")


def render_rating_widget(
    movie_id: int,
    key_prefix: str,
    current_rating: int | None = None,
) -> tuple[int, list[str], bool]:
    """Render the shared rating slider + mood pills widget.

    Displays a 0-100 slider with color-coded track, dot tick marks, dynamic
    sentiment label, and 7 Ekman mood reaction pills. Handles the touch
    guard (prevents accidental 0-ratings).

    Args:
        movie_id: TMDB movie ID (used for unique widget keys).
        key_prefix: Prefix for session state keys (e.g., "rate", "wl").
        current_rating: Pre-fill value for re-rating. None for first rating.

    Returns:
        Tuple of (rating, selected_moods, slider_ready).
        slider_ready is False until the user moves the slider.
    """
    # Track whether slider was moved — prevents accidental 0-ratings
    _touch_key = f"_{key_prefix}_touched_{movie_id}"
    st.session_state.setdefault(_touch_key, current_rating is not None)

    def _mark_touched() -> None:
        st.session_state[_touch_key] = True

    new_rating = st.slider(
        "Your rating",
        min_value=0, max_value=100,
        value=current_rating if current_rating is not None else 0,
        step=10, format="%d/100",
        key=f"{key_prefix}_rate_{movie_id}",
        on_change=_mark_touched,
    )

    # Dynamic sentiment label
    if new_rating == 0:
        _label = ""
    elif new_rating <= 20:
        _label = "Awful"
    elif new_rating <= 40:
        _label = "Poor"
    elif new_rating <= 60:
        _label = "Decent"
    elif new_rating <= 80:
        _label = "Great"
    else:
        _label = "Masterpiece"
    if _label:
        st.caption(_label, text_alignment="center")

    # Dynamic slider color: gray (0), red (<=33), orange (<=66), green (>66)
    if new_rating == 0:
        _color = "#d3d3d3"
    elif new_rating <= 33:
        _color = "#ff4b4b"
    elif new_rating <= 66:
        _color = "#ffa421"
    else:
        _color = "#21c354"
    _dots = ", ".join(
        f"radial-gradient(circle, rgba(255,255,255,0.6) 3px, transparent 3px) {i*10}% 50%"
        for i in range(11)
    )
    st.html(f"""<style>
        .stSlider > div > div > div > div {{
            background: {_color} !important;
        }}
        .stSlider [data-testid="stSliderTickBar"] {{
            background: none !important;
            background-image: none !important;
        }}
        .stSlider [data-testid="stSliderTickBar"]::before,
        .stSlider [data-testid="stSliderTickBar"]::after {{
            display: none !important;
        }}
        .stSlider [data-baseweb="slider"] > div {{
            position: relative !important;
        }}
        .stSlider [data-baseweb="slider"] > div::after {{
            content: '' !important;
            position: absolute !important;
            left: 0 !important; right: 0 !important; top: 50% !important;
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
    </style>""")

    # Mood reaction pills (optional, multi-select)
    st.caption("**How did this movie make you feel?** (optional)")
    _mood_options = [
        "Happy", "Interested", "Surprised", "Sad",
        "Disgusted", "Afraid", "Angry",
    ]
    selected_moods = st.pills(
        "Mood",
        options=_mood_options,
        selection_mode="multi",
        key=f"{key_prefix}_moods_{movie_id}",
        label_visibility="collapsed",
    )

    slider_ready = st.session_state.get(_touch_key, False)
    if not slider_ready:
        st.caption("Move the slider to set your rating", text_alignment="center")

    return new_rating, list(selected_moods or []), slider_ready
