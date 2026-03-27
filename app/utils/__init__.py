"""Utility modules for the movie recommender app.

Shared UI helpers used across multiple pages to avoid code duplication.
"""
from __future__ import annotations

from datetime import datetime

import requests
import streamlit as st

from app.utils.db import load_preference
from app.utils.tmdb import get_countries, poster_url


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


def _resolve_country_code() -> str:
    """Resolve the user's streaming country preference to an ISO 3166-1 code.

    Returns:
        Two-letter country code (e.g. "CH", "DE", "US"). Defaults to "CH".
    """
    pref_name = load_preference("streaming_country", "Switzerland")
    try:
        countries = get_countries()
        code = next(
            (c["iso_3166_1"] for c in countries
             if c.get("english_name") == pref_name),
            "CH",
        )
    except requests.RequestException:
        code = "CH"
    return code


def _format_release_date(details: dict, country_code: str) -> str | None:
    """Extract and format the release date for a specific country.

    Prefers the country-specific theatrical release (type 3) from the
    release_dates endpoint. Falls back to the global release_date field.

    Args:
        details: Full TMDB movie details dict.
        country_code: ISO 3166-1 country code.

    Returns:
        Formatted date string (e.g. "November 5, 2014") or None.
    """
    # Try country-specific release dates first
    release_dates_data = details.get("release_dates", {}).get("results", [])
    for country_entry in release_dates_data:
        if country_entry.get("iso_3166_1") == country_code:
            dates = country_entry.get("release_dates", [])
            # Prefer theatrical (type 3), then digital (4), then any
            for preferred_type in (3, 4):
                for rd in dates:
                    if rd.get("type") == preferred_type and rd.get("release_date"):
                        try:
                            dt = datetime.fromisoformat(
                                rd["release_date"].replace("Z", "+00:00"),
                            )
                            return dt.strftime("%B %-d, %Y")
                        except ValueError:
                            continue
            # Fallback: first available date for this country
            if dates and dates[0].get("release_date"):
                try:
                    dt = datetime.fromisoformat(
                        dates[0]["release_date"].replace("Z", "+00:00"),
                    )
                    return dt.strftime("%B %-d, %Y")
                except ValueError:
                    pass
            break
    # Global fallback: release_date from movie details
    global_date = details.get("release_date")
    if global_date:
        try:
            dt = datetime.strptime(global_date, "%Y-%m-%d")
            return dt.strftime("%B %-d, %Y")
        except ValueError:
            return global_date
    return None


def _find_best_trailer(details: dict) -> dict | None:
    """Find the best trailer from the videos results.

    Prefers official YouTube trailers, sorted by publish date (newest first).

    Args:
        details: Full TMDB movie details dict.

    Returns:
        Video dict with "key", "site", "name" etc., or None.
    """
    videos = details.get("videos", {}).get("results", [])
    # Filter for YouTube trailers only
    trailers = [
        v for v in videos
        if v.get("site") == "YouTube" and v.get("type") == "Trailer"
    ]
    if not trailers:
        return None
    # Sort: official first, then newest by publish date
    trailers.sort(
        key=lambda v: (v.get("official", False), v.get("published_at", "")),
        reverse=True,
    )
    return trailers[0]


def render_movie_detail_top(details: dict) -> None:
    """Render the upper half of the movie detail dialog.

    Displays the hero section (poster, title, genre, rating, runtime,
    release date, director, overview) followed by streaming providers
    and a Watch Now link. Called before page-specific action buttons.

    Args:
        details: Full TMDB movie details dict from get_movie_details().
    """
    country_code = _resolve_country_code()

    # === Hero section: poster + metadata ===
    col_poster, col_info = st.columns([1, 2])
    with col_poster:
        st.image(poster_url(details.get("poster_path"), size="w500"), width=250)
    with col_info:
        st.subheader(details.get("title", "Unknown"))
        # Tagline — marketing hook shown as italic subtitle
        tagline = details.get("tagline")
        if tagline:
            st.caption(f"*{tagline}*")
        # Genre badges
        genres = details.get("genres", [])
        if genres:
            st.caption("**Genre**")
            st.markdown(" ".join(f":gray-badge[{g['name']}]" for g in genres))
        # TMDB rating — always 1 decimal for consistency
        tmdb_rating = details.get("vote_average")
        st.caption(
            f"TMDB rating: {tmdb_rating:.1f} / 10" if tmdb_rating
            else "TMDB rating: N/A",
        )
        # Runtime + release date on one line
        meta_parts: list[str] = []
        runtime = details.get("runtime")
        if runtime:
            hours, mins = divmod(runtime, 60)
            meta_parts.append(
                f":material/schedule: {hours}h {mins}min" if hours
                else f":material/schedule: {mins} min",
            )
        release_str = _format_release_date(details, country_code)
        if release_str:
            meta_parts.append(f":material/calendar_month: {release_str}")
        if meta_parts:
            st.caption("  \u00b7  ".join(meta_parts))
        # Director
        crew = details.get("credits", {}).get("crew", [])
        directors = [c["name"] for c in crew if c.get("job") == "Director"]
        if directors:
            st.caption(f":material/movie: Directed by {', '.join(directors)}")
        # Overview
        st.write(details.get("overview", "No description available."))

    # === Streaming section: provider logos + Watch Now link ===
    providers_data = details.get("watch/providers", {}).get("results", {})
    country_data = providers_data.get(country_code, {})
    flatrate = country_data.get("flatrate", [])
    tmdb_link = country_data.get("link")
    if flatrate:
        st.caption("**Streaming**")
        provider_cols = st.columns(min(len(flatrate), 6))
        for i, p in enumerate(flatrate):
            with provider_cols[i % len(provider_cols)]:
                logo = poster_url(p.get("logo_path"), size="w92")
                if logo:
                    st.image(logo, width=40)
    if tmdb_link:
        st.link_button(
            "Watch Now",
            url=tmdb_link,
            icon=":material/play_circle:",
            use_container_width=True,
        )


def render_movie_detail_bottom(
    details: dict,
    *,
    show_trailer: bool = True,
    show_reviews: bool = True,
) -> None:
    """Render the lower half of the movie detail dialog.

    Displays trailer, cast, and reviews — called after page-specific
    action buttons. Sections are conditionally shown via parameters.

    Args:
        details: Full TMDB movie details dict from get_movie_details().
        show_trailer: Whether to show the YouTube trailer embed.
        show_reviews: Whether to show TMDB user reviews.
    """
    # === Trailer section: YouTube embed ===
    if show_trailer:
        trailer = _find_best_trailer(details)
        if trailer:
            st.caption("**Trailer**")
            st.video(f"https://www.youtube.com/watch?v={trailer['key']}")

    # === Cast section: top 5 billed actors with profile photos ===
    cast = details.get("credits", {}).get("cast", [])[:5]
    if cast:
        st.caption("**Cast**")
        cols = st.columns(5)
        for col, person in zip(cols, cast):
            with col:
                profile = person.get("profile_path")
                if profile:
                    st.image(poster_url(profile, size="w185"), width=100)
                else:
                    # Placeholder for actors without a profile photo
                    st.markdown(":material/person: ")
                st.caption(f"**{person.get('name', '')}**")

    # === Reviews section: up to 3 user reviews ===
    if show_reviews:
        reviews = details.get("reviews", {}).get("results", [])[:3]
        if reviews:
            st.caption("**Reviews**")
            for review in reviews:
                author = review.get("author", "Anonymous")
                rating = review.get("author_details", {}).get("rating")
                content = review.get("content", "")
                # Truncate long reviews to ~200 characters
                if len(content) > 200:
                    content = content[:200].rsplit(" ", 1)[0] + "..."
                # Rating star + author header
                header = (
                    f"\u2605 {rating:.0f}/10  \u00b7  {author}" if rating
                    else author
                )
                st.markdown(f"**{header}**")
                st.caption(content)
