"""Discover page — sidebar filters, mood pills, poster grid, ML scoring. See VIEWS.md."""
from __future__ import annotations

import requests
import streamlit as st
from src.constants import GENRE_ORDER, GRID_COLS, TMDB_PAGE_SIZE
from src.helpers import fetch_and_cache_details
from src.db import (
    load_preference,
    save_dismissed,
    save_to_watchlist,
)
from src.tmdb import (
    discover_movies_filtered,
    get_genre_map,
    get_languages,
    get_movie_details,
    poster_url,
    search_keywords,
)
from ml.scoring import filter_by_mood, get_or_compute_profile, score_candidates

# 7 Ekman mood categories (canonical source: ml.scoring.arrays.MOODS)
from ml.scoring.arrays import MOODS as _MOODS

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
_genre_names_ordered = [g for g in GENRE_ORDER if g in genre_map.values()]
# Reverse lookup: genre name → genre ID
_genre_name_to_id = {name: gid for gid, name in genre_map.items()}


# ============================================================
# SIDEBAR — Filter controls
# ============================================================

# --- Sidebar widget defaults (set once, then managed via session state) ---
# Using setdefault so _reset_sidebar() can write to session state without
# conflicting with widget `value=` parameters (Streamlit DuplicateValue warning).
st.session_state.setdefault("discover_genre", [])
st.session_state.setdefault("discover_year", (1900, 2026))
st.session_state.setdefault("discover_runtime", (0, 360))
st.session_state.setdefault("discover_rating", (0.0, 10.0))
st.session_state.setdefault("discover_min_votes", 50)
st.session_state.setdefault("discover_certification", "Any")
st.session_state.setdefault("discover_keyword_query", "")

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
        key="discover_year",
    )
    year_from = year_range[0] if year_range[0] > 1900 else None
    year_to = year_range[1] if year_range[1] < 2026 else None

    # --- Runtime range slider ---
    runtime_range = st.slider(
        "Runtime (min)", min_value=0, max_value=360,
        step=10, key="discover_runtime",
    )

    # --- Rating range slider ---
    rating_range = st.slider(
        "Rating", min_value=0.0, max_value=10.0,
        step=0.5, key="discover_rating",
    )

    # --- Min votes slider ---
    min_votes = st.slider(
        "Min votes", min_value=0, max_value=500,
        step=10, key="discover_min_votes",
    )

    # --- Age rating pills (DE certifications, exact match) ---
    # Why DE, not CH: see VIEWS.md
    _cert_country = "DE"
    _cert_options = ["Any", "0", "6", "12", "16", "18"]
    selected_cert = st.pills(
        "Age rating",
        options=_cert_options,
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
                             width="stretch"):
                    selected_keywords = [k for k in selected_keywords if k["id"] != kw["id"]]
                    st.session_state["_discover_keywords"] = selected_keywords
                    st.rerun()

    # --- Reset all button ---
    def _reset_sidebar():
        """Reset all sidebar filters to defaults."""
        # setdefault won't work — widgets recreate with stale values if key is missing
        st.session_state["discover_genre"] = []
        st.session_state["discover_year"] = (1900, 2026)
        st.session_state["discover_runtime"] = (0, 360)
        st.session_state["discover_rating"] = (0.0, 10.0)
        st.session_state["discover_min_votes"] = 50
        st.session_state["discover_keyword_query"] = ""
        st.session_state["discover_certification"] = "Any"
        st.session_state["_discover_keywords"] = []
        st.session_state["_discover_pages"] = 1

    st.button("Reset all", icon=":material/restart_alt:", on_click=_reset_sidebar,
              width="stretch")


# ============================================================
# MAIN PAGE — Sort, Mood, Poster Grid
# ============================================================

# --- Sort dropdown (right-aligned via spacer column) ---
col_spacer, col_sort = st.columns([3, 1])
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
    """Build TMDB discover params from current filter state."""
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
        params.append(("certification", selected_cert))

    # Streaming providers (from Settings subscriptions)
    _subs = st.session_state.get("subscriptions", set())
    if _subs:
        params.append(("with_watch_providers", "|".join(str(pid) for pid in _subs)))
        # Streaming country from Settings preference (resolved via shared helper)
        from src.helpers import resolve_country_code
        params.append(("watch_region", resolve_country_code()))
        params.append(("with_watch_monetization_types", "flatrate"))

    return params


# ============================================================
# FETCH MOVIES — Retrieval layer (TMDB API) + Ranking layer (ML)
# ============================================================

# Exclusion policy: rated + dismissed + watchlisted — see VIEWS.md
_dismissed = st.session_state.dismissed
_watchlisted_ids = {m["id"] for m in st.session_state.watchlist}
_rated_ids = st.session_state.ratings

_params = tuple(_build_discover_params())
_target_count = st.session_state._discover_pages * TMDB_PAGE_SIZE
movies: list[dict] = []
_has_more = True  # Whether TMDB has more pages available

try:
    _page = 0
    while len(movies) < _target_count and _has_more and _page < 10:
        _page += 1
        response = discover_movies_filtered(_params, page=_page)
        _page_movies = response.get("results", [])

        if not _page_movies:
            _has_more = False
            break

        _seen_ids = {m["id"] for m in movies}
        _page_movies = [
            m for m in _page_movies
            if m.get("poster_path")           # Must have a poster for the grid
            and m["id"] not in _seen_ids      # No cross-page duplicates
            and m["id"] not in _dismissed     # User said "not interested"
            and m["id"] not in _watchlisted_ids  # Already on watchlist
            and m["id"] not in _rated_ids     # Already rated
        ]
        movies.extend(_page_movies)

        # TMDB returns 20 results per full page; fewer means last page
        if len(_page_movies) < TMDB_PAGE_SIZE:
            _has_more = _page < 10

    # Trim to exact target count (may have fetched slightly more)
    movies = movies[:_target_count]

    # --- Mood filter (local) — see SCORING.md ---
    if selected_moods and movies:
        _filtered_ids = set(filter_by_mood(
            [m["id"] for m in movies], list(selected_moods),
        ))
        movies = [m for m in movies if m["id"] in _filtered_ids]

    # --- ML re-ranking (Personalized sort only) — see SCORING.md ---
    # Graceful degradation: no model/no ratings → API popularity order
    if sort_option == "Personalized" and movies:
        _profile = get_or_compute_profile(ratings=st.session_state.ratings)
        if _profile is not None:
            _scored = score_candidates(
                _profile, [m["id"] for m in movies],
                list(selected_moods) if selected_moods else None,
            )
            # Build score lookup and sort movies by ML score
            _id_to_score = {mid: score for mid, score in _scored}
            movies.sort(
                key=lambda m: _id_to_score.get(m["id"], 0.0), reverse=True,
            )

except requests.HTTPError as e:
    # 401 = invalid API key (common setup issue), other errors = transient
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
from src.components import inject_poster_grid_css
inject_poster_grid_css("discover_grid")


def _select_movie(movie_id: int) -> None:
    st.session_state._discover_selected_id = movie_id


def _load_more() -> None:
    st.session_state._discover_pages += 1


if movies:
    with st.container(key="discover_grid"):
        for row_start in range(0, len(movies), GRID_COLS):
            row_movies = movies[row_start:row_start + GRID_COLS]
            cols = st.columns(GRID_COLS)
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
                  on_click=_load_more, width="stretch",
                  type="primary")
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
                     and m["id"] not in _rated_ids][:TMDB_PAGE_SIZE]
        if _fallback:
            with st.container(key="discover_grid"):
                for row_start in range(0, len(_fallback), GRID_COLS):
                    row_movies = _fallback[row_start:row_start + GRID_COLS]
                    cols = st.columns(GRID_COLS)
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

# Trigger dialog after page renders (must be in main flow).
# Dialog is defined inline so the title can be set dynamically per movie.
if st.session_state._discover_selected_id is not None:
    _mid = st.session_state._discover_selected_id
    try:
        _details = get_movie_details(_mid)
    except requests.RequestException:
        st.error("Could not load movie details.", icon=":material/error:")
        st.stop()

    @st.dialog(_details.get("title", "Movie details"), width="large")
    def _show_discover_dialog() -> None:
        """Discover detail dialog: metadata, trailer, actions, reviews."""
        from src.components import render_discover_detail, render_movie_detail_bottom
        from src.helpers import find_best_trailer
        render_discover_detail(_details)

        # Trailer before action buttons (watch first, decide after)
        _trailer = find_best_trailer(_details)
        if _trailer:
            st.video(f"https://www.youtube.com/watch?v={_trailer['key']}")

        # Action buttons — if-st.button + st.rerun() because @st.dialog
        # inherits from @st.fragment (on_click only triggers fragment rerun)
        col_dismiss, col_watchlist = st.columns(2)
        with col_dismiss:
            if st.button("Not interested", icon=":material/thumb_down:",
                         width="stretch"):
                st.session_state.dismissed.add(_mid)
                save_dismissed(_mid)
                fetch_and_cache_details(_mid, _details)
                st.session_state._discover_selected_id = None
                st.session_state["_discover_toast"] = (
                    f"Skipped **{_details.get('title', '')}**",
                    ":material/thumb_down:",
                )
                st.rerun()
        with col_watchlist:
            if st.button("Add to watchlist", icon=":material/bookmark:",
                         type="primary", width="stretch"):
                _movie_dict = {
                    "id": _mid,
                    "title": _details.get("title", ""),
                    "poster_path": _details.get("poster_path"),
                    "vote_average": _details.get("vote_average"),
                    "overview": _details.get("overview"),
                    "genre_ids": [g["id"] for g in _details.get("genres", [])],
                }
                if _mid not in {m["id"] for m in st.session_state.watchlist}:
                    st.session_state.watchlist.append(_movie_dict)
                    save_to_watchlist(_movie_dict)
                fetch_and_cache_details(_mid, _details)
                st.session_state._discover_selected_id = None
                st.session_state["_discover_toast"] = (
                    f"Added **{_details.get('title', '')}** to watchlist",
                    ":material/bookmark:",
                )
                st.rerun()

        # Reviews below action buttons (trailer already shown above)
        render_movie_detail_bottom(
            _details, show_trailer=False, show_cast=False,
        )

    _show_discover_dialog()
