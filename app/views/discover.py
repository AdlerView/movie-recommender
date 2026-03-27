"""Discover page — Find new movies with sidebar filters and poster grid.

Sidebar layout with 12 filter controls (genre, year, runtime, rating,
min votes, keywords, language, certification, streaming). Main page shows
mood pills, sort dropdown, and a clickable poster grid (5 columns).
Live filtering: grid updates on every filter/mood/sort change.

This is the only page with a sidebar. Filters are collapsible via
Streamlit's native sidebar toggle. Detail dialog on poster click shows
movie info with "Add to watchlist" and "Not interested" actions.
"""
from __future__ import annotations

import requests
import streamlit as st
from app.utils.db import (
    load_preference,
    save_dismissed,
    save_to_watchlist,
)
from app.utils.tmdb import (
    discover_movies_filtered,
    get_certifications,
    get_countries,
    get_genre_map,
    get_languages,
    get_movie_details,
    poster_url,
    search_keywords,
)
from ml.scoring import filter_by_mood, get_or_compute_profile, score_candidates

# --- Constants ---

# Number of columns in the poster grid
_GRID_COLS = 5
# Movies per TMDB API page
_TMDB_PAGE_SIZE = 20
# 7 Ekman mood categories
_MOODS = ["Happy", "Interested", "Surprised", "Sad", "Disgusted", "Afraid", "Angry"]
# Genre pill order optimized for sidebar width (shorter names grouped together)
_GENRE_ORDER = [
    "War", "Music", "Crime",
    "Drama", "Horror", "Family",
    "Action", "Comedy", "History",
    "Western", "Mystery", "Fantasy",
    "Romance", "Thriller", "Adventure",
    "Animation", "TV Movie", "Documentary",
    "Science Fiction",
]

# --- State initialization ---
st.session_state.setdefault("_discover_pages", 1)
st.session_state.setdefault("_discover_selected_id", None)

# --- Deferred toast (shown after rerun following a save action) ---
if "_discover_toast" in st.session_state:
    _toast_msg, _toast_icon = st.session_state.pop("_discover_toast")
    st.toast(_toast_msg, icon=_toast_icon)

# --- Load TMDB configuration data (cached 24h) ---
try:
    genre_map = get_genre_map()
except requests.RequestException:
    st.error("Could not connect to TMDB. Check your internet connection.",
             icon=":material/wifi_off:")
    st.stop()

# Sort genre names by the width-optimized order defined above
_genre_names_ordered = [g for g in _GENRE_ORDER if g in genre_map.values()]
# Reverse lookup: genre name → genre ID
_genre_name_to_id = {name: gid for gid, name in genre_map.items()}


# ============================================================
# SIDEBAR — Filter controls
# ============================================================

with st.sidebar:
    st.header("Filters")

    # --- Genre (st.pills, multi-select, width-optimized order) ---
    selected_genres = st.pills(
        "Genre",
        options=_genre_names_ordered,
        selection_mode="multi",
        key="discover_genre",
    )

    # --- Year range (slider instead of number_input — steppers work reliably) ---
    year_range = st.slider(
        "Year", min_value=1900, max_value=2026,
        value=(1900, 2026), key="discover_year",
    )
    year_from = year_range[0] if year_range[0] > 1900 else None
    year_to = year_range[1] if year_range[1] < 2026 else None

    # --- Runtime range slider ---
    runtime_range = st.slider(
        "Runtime (min)", min_value=0, max_value=360,
        value=(0, 360), step=10, key="discover_runtime",
    )

    # --- Rating range slider ---
    rating_range = st.slider(
        "Rating", min_value=0.0, max_value=10.0,
        value=(0.0, 10.0), step=0.5, key="discover_rating",
    )

    # --- Min votes slider ---
    min_votes = st.slider(
        "Min votes", min_value=0, max_value=500,
        value=50, step=10, key="discover_min_votes",
    )

    # --- Certification dropdown ---
    _cert_country = "DE"
    try:
        _certs = get_certifications(_cert_country)
        _cert_options = ["Any"] + [c["certification"] for c in
                                   sorted(_certs, key=lambda x: x.get("order", 0))
                                   if c["certification"]]
    except requests.RequestException:
        _cert_options = ["Any"]
    selected_cert = st.selectbox(
        f"Certification ({_cert_country})", options=_cert_options,
        key="discover_certification",
    )

    # --- Keywords (autocomplete search) ---
    keyword_query = st.text_input(
        "Keywords", placeholder="Search keywords...",
        key="discover_keyword_query", label_visibility="visible",
    )
    # Fetch keyword suggestions from TMDB API
    _keyword_suggestions = []
    if keyword_query and len(keyword_query.strip()) >= 2:
        try:
            _keyword_suggestions = search_keywords(keyword_query.strip())
        except requests.RequestException:
            pass
    # Show suggestions as selectable options
    selected_keywords: list[dict] = st.session_state.get("_discover_keywords", [])
    if _keyword_suggestions:
        _kw_options = {kw["name"]: kw for kw in _keyword_suggestions
                       if kw["id"] not in {k["id"] for k in selected_keywords}}
        if _kw_options:
            chosen = st.pills(
                "Add keyword",
                options=list(_kw_options.keys()),
                key=f"discover_kw_suggest_{keyword_query}",
                label_visibility="collapsed",
            )
            if chosen:
                selected_keywords.append(_kw_options[chosen])
                st.session_state["_discover_keywords"] = selected_keywords
                st.rerun()
    # Show selected keywords as removable chips
    if selected_keywords:
        _cols = st.columns(len(selected_keywords))
        for i, kw in enumerate(selected_keywords):
            with _cols[i]:
                if st.button(f"✕ {kw['name']}", key=f"discover_kw_rm_{kw['id']}",
                             use_container_width=True):
                    selected_keywords = [k for k in selected_keywords if k["id"] != kw["id"]]
                    st.session_state["_discover_keywords"] = selected_keywords
                    st.rerun()

    # --- Reset all button ---
    def _reset_sidebar():
        """Reset all sidebar filter states to defaults.

        Sets explicit default values instead of popping keys, because
        Streamlit widgets recreate with stale values if the key is
        missing but the widget still renders.
        """
        # Pills widgets: set to empty list for multi-select
        st.session_state["discover_genre"] = []
        # Sliders: set to full range (= no filter)
        st.session_state["discover_year"] = (1900, 2026)
        st.session_state["discover_runtime"] = (0, 360)
        st.session_state["discover_rating"] = (0.0, 10.0)
        st.session_state["discover_min_votes"] = 50
        # Text input: clear
        st.session_state["discover_keyword_query"] = ""
        # Selectbox: set to first option (= "Any")
        st.session_state["discover_certification"] = "Any"
        # Keywords list and pagination
        st.session_state["_discover_keywords"] = []
        st.session_state["_discover_pages"] = 1

    st.button("Reset all", icon=":material/restart_alt:", on_click=_reset_sidebar,
              use_container_width=True)


# ============================================================
# MAIN PAGE — Header, Mood, Sort, Poster Grid
# ============================================================

st.header("Which movie will you watch?", divider="gray", text_alignment="center")

# --- Sort + section heading on same line ---
col_heading, col_sort = st.columns([3, 1])
with col_heading:
    st.subheader("Recommended Movies")
with col_sort:
    sort_option = st.selectbox(
        "Sort",
        options=["Personalized", "Popularity", "Rating", "Release date"],
        key="discover_sort",
        label_visibility="collapsed",
    )

# --- Mood pills (main page, toggle-deselect behavior) ---
selected_moods = st.pills(
    "Mood",
    options=_MOODS,
    selection_mode="multi",
    key="discover_mood",
    label_visibility="collapsed",
)


# ============================================================
# BUILD TMDB API PARAMETERS from filter state
# ============================================================

def _build_discover_params() -> list[tuple[str, str]]:
    """Build TMDB discover/movie API parameters from current filter state.

    Returns:
        List of (key, value) tuples for the API call.
    """
    params: list[tuple[str, str]] = []

    # Sort mapping
    sort_map = {
        "Personalized": "popularity.desc",  # ML re-ranking happens later
        "Popularity": "popularity.desc",
        "Rating": "vote_average.desc",
        "Release date": "primary_release_date.desc",
    }
    params.append(("sort_by", sort_map.get(sort_option, "popularity.desc")))

    # Genre filter (AND logic via comma-separated IDs)
    if selected_genres:
        genre_ids = [str(_genre_name_to_id[g]) for g in selected_genres
                     if g in _genre_name_to_id]
        if genre_ids:
            params.append(("with_genres", ",".join(genre_ids)))

    # Year range
    if year_from:
        params.append(("primary_release_date.gte", f"{year_from}-01-01"))
    if year_to:
        params.append(("primary_release_date.lte", f"{year_to}-12-31"))

    # Runtime range (only if not full range)
    if runtime_range != (0, 360):
        params.append(("with_runtime.gte", str(runtime_range[0])))
        params.append(("with_runtime.lte", str(runtime_range[1])))

    # Rating range (only if not full range)
    if rating_range != (0.0, 10.0):
        params.append(("vote_average.gte", str(rating_range[0])))
        params.append(("vote_average.lte", str(rating_range[1])))

    # Minimum votes
    if min_votes > 0:
        params.append(("vote_count.gte", str(min_votes)))

    # Keywords (OR logic via pipe-separated IDs)
    if selected_keywords:
        kw_ids = "|".join(str(kw["id"]) for kw in selected_keywords)
        params.append(("with_keywords", kw_ids))

    # Language (from Settings preference)
    _pref_lang = load_preference("preferred_language")
    if _pref_lang and _pref_lang != "Any":
        try:
            _langs = get_languages()
            _lang_code = next(
                (lg["iso_639_1"] for lg in _langs
                 if lg.get("english_name") == _pref_lang),
                None,
            )
            if _lang_code:
                params.append(("with_original_language", _lang_code))
        except requests.RequestException:
            pass

    # Certification
    if selected_cert and selected_cert != "Any":
        params.append(("certification_country", _cert_country))
        params.append(("certification.lte", selected_cert))

    # Streaming providers (from Settings subscriptions)
    _subs = st.session_state.get("subscriptions", set())
    if _subs:
        params.append(("with_watch_providers", "|".join(str(pid) for pid in _subs)))
        # Streaming country from Settings preference
        _pref_country = load_preference("streaming_country", "Switzerland")
        try:
            _countries_list = get_countries()
            _code = next(
                (c["iso_3166_1"] for c in _countries_list
                 if c.get("english_name") == _pref_country),
                "CH",
            )
        except requests.RequestException:
            _code = "CH"
        params.append(("watch_region", _code))
        params.append(("with_watch_monetization_types", "flatrate"))

    return params


# ============================================================
# FETCH MOVIES
# ============================================================

# Sets for filtering out already-seen movies
_dismissed = st.session_state.dismissed
_watchlisted_ids = {m["id"] for m in st.session_state.watchlist}
_rated_ids = st.session_state.ratings

# Build API parameters and fetch movies
_params = tuple(_build_discover_params())
_target_count = st.session_state._discover_pages * _TMDB_PAGE_SIZE
movies: list[dict] = []
_has_more = True

try:
    _page = 0
    while len(movies) < _target_count and _has_more and _page < 10:
        _page += 1
        # Always use discover endpoint (params always non-empty: sort_by + vote_count)
        response = discover_movies_filtered(_params, page=_page)
        _page_movies = response.get("results", [])

        if not _page_movies:
            _has_more = False
            break

        # Filter: remove poster-less, duplicates, and already-seen movies
        _seen_ids = {m["id"] for m in movies}
        _page_movies = [
            m for m in _page_movies
            if m.get("poster_path")
            and m["id"] not in _seen_ids
            and m["id"] not in _dismissed
            and m["id"] not in _watchlisted_ids
            and m["id"] not in _rated_ids
        ]
        movies.extend(_page_movies)

        if len(_page_movies) < _TMDB_PAGE_SIZE:
            _has_more = _page < 10

    movies = movies[:_target_count]

    # --- Mood filter (applies to ALL sort orders) ---
    if selected_moods and movies:
        _filtered_ids = set(filter_by_mood(
            [m["id"] for m in movies], list(selected_moods),
        ))
        movies = [m for m in movies if m["id"] in _filtered_ids]

    # --- Personalized ranking (only for "Personalized" sort) ---
    if sort_option == "Personalized" and movies:
        _profile = get_or_compute_profile(ratings=st.session_state.ratings)
        if _profile is not None:
            _scored = score_candidates(
                _profile, [m["id"] for m in movies],
                list(selected_moods) if selected_moods else None,
            )
            _id_to_score = {mid: score for mid, score in _scored}
            movies.sort(
                key=lambda m: _id_to_score.get(m["id"], 0.0), reverse=True,
            )

except requests.HTTPError as e:
    if e.response is not None and e.response.status_code == 401:
        st.error("Invalid TMDB API key. Check `.streamlit/secrets.toml`.",
                 icon=":material/key_off:")
    else:
        st.error("TMDB API error. Please try again later.", icon=":material/error:")
    st.stop()
except requests.ConnectionError:
    st.error("Could not connect to TMDB.", icon=":material/wifi_off:")
    st.stop()


# ============================================================
# POSTER GRID
# ============================================================

# Poster grid CSS (shared helper, scoped to container key)
from app.utils import inject_poster_grid_css
inject_poster_grid_css("discover_grid")


def _select_movie(movie_id: int) -> None:
    """Set the selected movie ID to trigger the detail dialog."""
    st.session_state._discover_selected_id = movie_id


def _load_more() -> None:
    """Load the next page of results."""
    st.session_state._discover_pages += 1


if movies:
    with st.container(key="discover_grid"):
        for row_start in range(0, len(movies), _GRID_COLS):
            row_movies = movies[row_start:row_start + _GRID_COLS]
            cols = st.columns(_GRID_COLS)
            for col, movie in zip(cols, row_movies):
                with col:
                    st.image(poster_url(movie.get("poster_path"), size="w342"))
                    st.button(
                        "View",
                        key=f"discover_sel_{movie['id']}",
                        on_click=_select_movie,
                        args=(movie["id"],),
                    )

    # Load more button
    if _has_more:
        st.button("Load more", icon=":material/expand_more:",
                  on_click=_load_more, use_container_width=True)
else:
    # Empty results — show info and fallback recommendations
    st.info("No movies match your filters. Try fewer criteria.",
            icon=":material/search_off:")

    st.subheader("You might also like")
    try:
        _fallback_resp = discover_movies_filtered(
            (("sort_by", "popularity.desc"), ("vote_count.gte", "50")), page=1,
        )
        _fallback = _fallback_resp.get("results", [])
        _fallback = [m for m in _fallback if m.get("poster_path")
                     and m["id"] not in _dismissed
                     and m["id"] not in _watchlisted_ids
                     and m["id"] not in _rated_ids][:_TMDB_PAGE_SIZE]
        if _fallback:
            with st.container(key="discover_grid"):
                for row_start in range(0, len(_fallback), _GRID_COLS):
                    row_movies = _fallback[row_start:row_start + _GRID_COLS]
                    cols = st.columns(_GRID_COLS)
                    for col, movie in zip(cols, row_movies):
                        with col:
                            st.image(poster_url(movie.get("poster_path"), size="w342"))
                            st.button(
                                "View",
                                key=f"discover_fb_{movie['id']}",
                                on_click=_select_movie,
                                args=(movie["id"],),
                            )
    except requests.RequestException:
        pass


# ============================================================
# DETAIL DIALOG (triggered by poster click)
# ============================================================

@st.dialog("Movie details", width="large")
def _show_detail_dialog(movie_id: int) -> None:
    """Show movie detail dialog with watchlist and dismiss actions.

    Args:
        movie_id: TMDB movie ID to display.
    """
    try:
        details = get_movie_details(movie_id)
    except requests.RequestException:
        st.error("Could not load movie details.", icon=":material/error:")
        return

    # Movie info card
    col_poster, col_info = st.columns([1, 2])
    with col_poster:
        st.image(poster_url(details.get("poster_path"), size="w500"), width=250)
    with col_info:
        st.subheader(details.get("title", "Unknown"))
        # Genre badges
        genres = details.get("genres", [])
        if genres:
            st.caption("**Genre**")
            st.markdown(" ".join(f":gray-badge[{g['name']}]" for g in genres))
        # TMDB rating
        _tmdb = details.get("vote_average")
        st.caption(f"TMDB rating: {_tmdb:.1f} / 10" if _tmdb else "TMDB rating: N/A")
        # Runtime
        runtime = details.get("runtime")
        if runtime:
            hours, mins = divmod(runtime, 60)
            st.caption(f":material/schedule: {hours}h {mins}min" if hours
                       else f":material/schedule: {mins} min")
        # Overview
        st.write(details.get("overview", "No description available."))

    # Streaming providers (country from Settings preference)
    _providers = details.get("watch/providers", {}).get("results", {})
    _pref_country_name = load_preference("streaming_country", "Switzerland")
    try:
        _country_list = get_countries()
        _dialog_country_code = next(
            (c["iso_3166_1"] for c in _country_list
             if c.get("english_name") == _pref_country_name),
            "CH",
        )
    except requests.RequestException:
        _dialog_country_code = "CH"
    _country_data = _providers.get(_dialog_country_code, {})
    _flatrate = _country_data.get("flatrate", [])
    if _flatrate:
        st.caption("**Streaming**")
        _provider_cols = st.columns(len(_flatrate))
        for i, p in enumerate(_flatrate):
            with _provider_cols[i]:
                _logo = poster_url(p.get("logo_path"), size="w92")
                if _logo:
                    st.image(_logo, width=40)
                st.caption(p["provider_name"])

    st.divider()

    # Action buttons — use if-st.button + st.rerun() instead of on_click
    # callbacks, because @st.dialog inherits from @st.fragment and on_click
    # only triggers a fragment rerun (dialog stays open, main page unchanged).
    col_dismiss, col_watchlist = st.columns(2)
    with col_dismiss:
        if st.button("Not interested", icon=":material/thumb_down:",
                     use_container_width=True):
            st.session_state.dismissed.add(movie_id)
            save_dismissed(movie_id)
            st.session_state._discover_selected_id = None
            st.session_state["_discover_toast"] = (
                f"Skipped **{details.get('title', '')}**",
                ":material/thumb_down:",
            )
            st.rerun()
    with col_watchlist:
        if st.button("Add to watchlist", icon=":material/bookmark:",
                     type="primary", use_container_width=True):
            _movie_dict = {
                "id": movie_id,
                "title": details.get("title", ""),
                "poster_path": details.get("poster_path"),
                "vote_average": details.get("vote_average"),
                "overview": details.get("overview"),
                "genre_ids": [g["id"] for g in details.get("genres", [])],
            }
            # Guard: prevent duplicate entries in watchlist
            if movie_id not in {m["id"] for m in st.session_state.watchlist}:
                st.session_state.watchlist.append(_movie_dict)
                save_to_watchlist(_movie_dict)
            st.session_state._discover_selected_id = None
            st.session_state["_discover_toast"] = (
                f"Added **{details.get('title', '')}** to watchlist",
                ":material/bookmark:",
            )
            st.rerun()


# Trigger dialog after page renders (must be in main flow)
if st.session_state._discover_selected_id is not None:
    _show_detail_dialog(st.session_state._discover_selected_id)
