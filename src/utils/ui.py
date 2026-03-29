"""Streamlit UI renderers. All functions here use st.* directly. See VIEWS.md."""
from __future__ import annotations

import streamlit as st

from src.utils.helpers import (
    fetch_and_cache_details,  # noqa: F401 (re-exported via __init__)
    find_best_trailer,
    format_release_date,
    rating_color,
    resolve_country_code,
)
from src.utils.tmdb import poster_url


def inject_poster_grid_css(container_key: str, gap: str | None = None) -> None:
    """Inject CSS for clickable poster grid with invisible button overlays."""
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

    from ml.scoring.arrays import MOODS

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
            count = person["movies"]
            avg = person["avg_rating"]
            _rc = rating_color(avg)
            st.caption(
                f'**{person["name"]}**  \n'
                f'{count} {"movie" if count == 1 else "movies"}'
                f' · :color[{avg:.0f}/100]{{foreground="{_rc}"}}'
            )


def render_discover_detail(details: dict) -> None:
    """Render Discover detail: metadata left, cast photos right. See VIEWS.md."""
    country_code = resolve_country_code()

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
        release_str = format_release_date(details, country_code)
        if release_str:
            meta_parts.append(f":material/calendar_month: {release_str}")
        if meta_parts:
            st.caption("  \u00b7  ".join(meta_parts))
        tagline = details.get("tagline")
        if tagline:
            st.caption(f"*{tagline}*")
        # Genre + TMDB rating badges on one line
        genres = details.get("genres", [])
        tmdb_rating = details.get("vote_average")
        genre_str = " ".join(f":gray-badge[{g['name']}]" for g in genres)
        if tmdb_rating:
            _rc = rating_color(tmdb_rating, scale=10)
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
        crew = details.get("credits", {}).get("crew", [])
        directors = [c["name"] for c in crew if c.get("job") == "Director"]
        if directors:
            st.caption(f":material/movie: Directed by {', '.join(directors)}")
        st.write(details.get("overview", "No description available."))
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
    country_code = resolve_country_code()

    providers_data = details.get("watch/providers", {}).get("results", {})
    country_data = providers_data.get(country_code, {})
    flatrate = country_data.get("flatrate", [])
    runtime = details.get("runtime")
    if flatrate:
        logo_cols = st.columns(min(len(flatrate), 6))
        for i, p in enumerate(flatrate):
            with logo_cols[i % len(logo_cols)]:
                logo = poster_url(p.get("logo_path"), size="w92")
                if logo:
                    st.image(logo, width=40)
    if runtime:
        hours, mins = divmod(runtime, 60)
        st.caption(
            f":material/schedule: {hours}h {mins}min" if hours
            else f":material/schedule: {mins} min",
        )

    trailer = find_best_trailer(details)
    if trailer:
        st.video(f"https://www.youtube.com/watch?v={trailer['key']}")

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
    if show_trailer:
        trailer = find_best_trailer(details)
        if trailer:
            st.video(f"https://www.youtube.com/watch?v={trailer['key']}")

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
