"""Shared UI helpers and constants. Renderer details: see VIEWS.md."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Final

import requests
import streamlit as st

from app.utils.db import load_preference
from app.utils.tmdb import get_countries, get_movie_keywords, poster_url

# ---------------------------------------------------------------------------
# Shared constants (used by discover.py, rate.py, watchlist.py)
# ---------------------------------------------------------------------------

# Number of columns in the poster grid across all pages
GRID_COLS: Final[int] = 5
# Movies per TMDB API page (fixed by TMDB, not configurable)
TMDB_PAGE_SIZE: Final[int] = 20
# Default streaming country (used as fallback in multiple places)
DEFAULT_COUNTRY_NAME: Final[str] = "Switzerland"
DEFAULT_COUNTRY_CODE: Final[str] = "CH"

# 5-level rating color scale (0-100): used for slider, badges, person rankings
# Red → Orange → Yellow → Light green → Green
RATING_COLORS: Final[list[tuple[int, str]]] = [
    (20, "#ff4b4b"),   # 0-20: Awful (red)
    (40, "#ffa421"),   # 21-40: Poor (orange)
    (60, "#e8c840"),   # 41-60: Decent (yellow)
    (80, "#85cc5a"),   # 61-80: Great (light green)
    (100, "#21c354"),  # 81-100: Masterpiece (green)
]

# Mood colors (Ekman model) — canonical source for charts, pills, and badges
MOOD_COLORS: Final[dict[str, str]] = {
    "Happy": "#FFD700",       # Gold — warmth, joy
    "Interested": "#1c83e1",  # Blue — curiosity, thought
    "Surprised": "#ffa421",   # Orange — unexpected
    "Sad": "#6c8ebf",         # Muted blue — melancholy
    "Disgusted": "#803df5",   # Purple — visceral revulsion
    "Afraid": "#ff4b4b",      # Red — danger, alarm
    "Angry": "#cc0000",       # Dark red — intensity, aggression
}


def rating_color(value: int | float, scale: int = 100) -> str:
    """Return hex color for a rating value (5-level scale, normalized via scale param)."""
    normalized = (value / scale) * 100 if scale != 100 else value
    for threshold, color in RATING_COLORS:
        if normalized <= threshold:
            return color
    return RATING_COLORS[-1][1]


def inject_poster_grid_css(container_key: str, gap: str | None = None) -> None:
    """Inject CSS for clickable poster grid with invisible button overlays."""
    # Optional gap override for compact grids (e.g., Settings provider logos)
    gap_css = (
        f".st-key-{container_key} [data-testid=\"stHorizontalBlock\"] "
        f"{{ gap: {gap} !important; }}\n        " if gap else ""
    )
    st.html(f"""<style>
        {gap_css}.st-key-{container_key} [data-testid="stColumn"] {{
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
    """Rating slider + mood pills. Returns (rating, selected_moods, slider_ready)."""
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

    # Dynamic sentiment label with matching color
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
        _lbl_color = rating_color(new_rating)
        st.markdown(
            f':color[{_label}]{{foreground="{_lbl_color}"}}',
            text_alignment="center",
        )

    # Dynamic slider color: gray (0), 5-level scale (1-100)
    _color = "#d3d3d3" if new_rating == 0 else rating_color(new_rating)
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
    from ml.scoring.user_profile import MOODS

    st.caption("**How did this movie make you feel?** (optional)")
    selected_moods = st.pills(
        "Mood",
        options=MOODS,
        selection_mode="multi",
        key=f"{key_prefix}_moods_{movie_id}",
        label_visibility="collapsed",
    )

    slider_ready = st.session_state.get(_touch_key, False)
    if not slider_ready:
        st.caption("Move the slider to set your rating", text_alignment="center")

    return new_rating, list(selected_moods or []), slider_ready


def fetch_and_cache_details(movie_id: int, details: dict) -> None:
    """Fetch keywords and cache details + keywords to SQLite (best-effort)."""
    from app.utils.db import save_movie_details

    # Fetch keywords separately (not included in append_to_response)
    try:
        keywords = get_movie_keywords(movie_id)
    except requests.RequestException:
        keywords = None
    # Save details + keywords to SQLite (idempotent INSERT OR REPLACE)
    try:
        save_movie_details(movie_id, details, keywords=keywords)
    except sqlite3.Error:
        pass  # Best-effort caching — app works without it


def render_person_ranking(
    persons: list[dict],
    label: str,
) -> None:
    """Render ranked persons with photos, movie count, avg rating."""
    if not persons:
        return
    cols = st.columns(len(persons))
    for i, person in enumerate(persons):
        with cols[i]:
            photo = poster_url(person["profile_path"], size="w185")
            if photo:
                st.image(photo, width=100)
            # Format: "Name\nN movies · colored rating/100"
            count = person["movies"]
            avg = person["avg_rating"]
            _rc = rating_color(avg)
            st.caption(
                f'**{person["name"]}**  \n'
                f'{count} {"movie" if count == 1 else "movies"}'
                f' · :color[{avg:.0f}/100]{{foreground="{_rc}"}}'
            )


def _resolve_country_code() -> str:
    """Resolve streaming country preference to ISO 3166-1 code."""
    pref_name = load_preference("streaming_country", DEFAULT_COUNTRY_NAME)
    try:
        countries = get_countries()
        code = next(
            (c["iso_3166_1"] for c in countries
             if c.get("english_name") == pref_name),
            DEFAULT_COUNTRY_CODE,
        )
    except requests.RequestException:
        code = DEFAULT_COUNTRY_CODE
    return code


def _format_release_date(details: dict, country_code: str) -> str | None:
    """Format release date: country-specific type 3 (theatrical) → type 4 (digital) → global fallback."""
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


def find_best_trailer(details: dict) -> dict | None:
    """Find best YouTube trailer (official first, newest first)."""
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


def render_discover_detail(details: dict) -> None:
    """Render Discover detail: metadata left, cast photos right. See VIEWS.md."""
    country_code = _resolve_country_code()

    col_info, col_cast = st.columns([3, 2])

    # === Left column: metadata ===
    with col_info:
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
        # Tagline
        tagline = details.get("tagline")
        if tagline:
            st.caption(f"*{tagline}*")
        # Genre + TMDB rating badges on one line
        genres = details.get("genres", [])
        tmdb_rating = details.get("vote_average")
        genre_str = " ".join(f":gray-badge[{g['name']}]" for g in genres)
        if tmdb_rating:
            _rc = rating_color(tmdb_rating, scale=10)
            # Map hex to closest Streamlit badge color name
            if _rc in ("#21c354", "#85cc5a"):
                rating_str = f"  :green-badge[{tmdb_rating:.1f}]"
            elif _rc in ("#ffa421", "#e8c840"):
                rating_str = f"  :orange-badge[{tmdb_rating:.1f}]"
            else:
                rating_str = f"  :red-badge[{tmdb_rating:.1f}]"
        else:
            rating_str = ""
        if genre_str or rating_str:
            st.markdown(f"{genre_str}{rating_str}")
        # Director
        crew = details.get("credits", {}).get("crew", [])
        directors = [c["name"] for c in crew if c.get("job") == "Director"]
        if directors:
            st.caption(f":material/movie: Directed by {', '.join(directors)}")
        # Overview
        st.write(details.get("overview", "No description available."))
        # Streaming provider logo (no header, no label)
        providers_data = details.get("watch/providers", {}).get("results", {})
        country_data = providers_data.get(country_code, {})
        flatrate = country_data.get("flatrate", [])
        if flatrate:
            logo_cols = st.columns(min(len(flatrate), 6))
            for i, p in enumerate(flatrate):
                with logo_cols[i % len(logo_cols)]:
                    logo = poster_url(p.get("logo_path"), size="w92")
                    if logo:
                        st.image(logo, width=40)

    # === Right column: cast photos ===
    with col_cast:
        cast = details.get("credits", {}).get("cast", [])[:5]
        if cast:
            cast_cols = st.columns(5)
            for i, person in enumerate(cast):
                with cast_cols[i]:
                    profile = person.get("profile_path")
                    if profile:
                        st.image(poster_url(profile, size="w185"), width=80)


def render_watchlist_detail(details: dict) -> None:
    """Render Watchlist detail: providers, runtime, trailer, Watch Now. See VIEWS.md."""
    country_code = _resolve_country_code()

    # Runtime + streaming logos on one row
    providers_data = details.get("watch/providers", {}).get("results", {})
    country_data = providers_data.get(country_code, {})
    flatrate = country_data.get("flatrate", [])
    runtime = details.get("runtime")
    # Provider logos stacked directly under dialog title
    if flatrate:
        logo_cols = st.columns(min(len(flatrate), 6))
        for i, p in enumerate(flatrate):
            with logo_cols[i % len(logo_cols)]:
                logo = poster_url(p.get("logo_path"), size="w92")
                if logo:
                    st.image(logo, width=40)
    # Runtime below providers
    if runtime:
        hours, mins = divmod(runtime, 60)
        st.caption(
            f":material/schedule: {hours}h {mins}min" if hours
            else f":material/schedule: {mins} min",
        )

    # Trailer (no header — flows directly under runtime/logos)
    trailer = find_best_trailer(details)
    if trailer:
        st.video(f"https://www.youtube.com/watch?v={trailer['key']}")

    # Watch Now link
    tmdb_link = country_data.get("link")
    if tmdb_link:
        st.link_button(
            "Watch Now",
            url=tmdb_link,
            icon=":material/play_circle:",
            width="stretch",
        )



def render_movie_detail_bottom(
    details: dict,
    *,
    show_trailer: bool = True,
    show_cast: bool = True,
    show_reviews: bool = True,
) -> None:
    """Render trailer, cast, reviews below action buttons."""
    # === Trailer section: YouTube embed ===
    if show_trailer:
        trailer = find_best_trailer(details)
        if trailer:
            st.video(f"https://www.youtube.com/watch?v={trailer['key']}")

    # === Cast section: top 5 billed actors with profile photos ===
    if show_cast:
        cast = details.get("credits", {}).get("cast", [])[:5]
        if cast:
            cols = st.columns(5)
            for col, person in zip(cols, cast):
                with col:
                    profile = person.get("profile_path")
                    if profile:
                        st.image(poster_url(profile, size="w185"), width=100)
                    else:
                        st.markdown(":material/person: ")
                    st.caption(f"**{person.get('name', '')}**")

    # === Reviews section: up to 3, separated by dividers ===
    if show_reviews:
        reviews = details.get("reviews", {}).get("results", [])[:3]
        for review in reviews:
            author = review.get("author", "Anonymous")
            rating = review.get("author_details", {}).get("rating")
            content = review.get("content", "")
            header = (
                f"\u2605 {rating:.0f}/10  \u00b7  {author}" if rating
                else author
            )
            with st.expander(header):
                st.caption(content)
