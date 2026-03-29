"""Settings page — streaming country, subscriptions, language. See VIEWS.md."""
from __future__ import annotations

import requests
import streamlit as st
from app.utils import DEFAULT_COUNTRY_CODE, DEFAULT_COUNTRY_NAME
from app.utils.db import (
    delete_preference,
    load_preference,
    save_preference,
    save_subscriptions,
)
from app.utils.tmdb import get_countries, get_languages, get_watch_providers_list, poster_url

# --- Deferred toast (st.toast before st.rerun is lost) ---
if "_settings_toast" in st.session_state:
    _msg, _icon = st.session_state.pop("_settings_toast")
    st.toast(_msg, icon=_icon)

# ============================================================
# STREAMING COUNTRY
# ============================================================

st.subheader("Streaming country")

# Load saved country (default: Switzerland)
_saved_country = load_preference("streaming_country", DEFAULT_COUNTRY_NAME)

# Fetch country list from TMDB (cached 24h). Graceful degradation: if the
# API is unreachable, show only the default country as a fallback option.
try:
    _countries = get_countries()
    # Deduplicate and sort alphabetically for the dropdown
    _country_names = sorted(
        {c["english_name"] for c in _countries if c.get("english_name")},
    )
    # Build name→code lookup for resolving the selected country to an ISO code
    _country_code_map = {c["english_name"]: c["iso_3166_1"] for c in _countries}
except requests.RequestException:
    _country_names = [DEFAULT_COUNTRY_NAME]
    _country_code_map = {DEFAULT_COUNTRY_NAME: DEFAULT_COUNTRY_CODE}

# Pre-select the saved country in the dropdown (fallback: first item)
_country_idx = (
    _country_names.index(_saved_country)
    if _saved_country in _country_names else 0
)


def _on_country_change() -> None:
    _val = st.session_state.get("settings_country", DEFAULT_COUNTRY_NAME)
    save_preference("streaming_country", _val)
    # Reset provider init so grid reloads for the new country
    st.session_state.pop("_settings_subs_init", None)
    st.session_state["_settings_toast"] = (
        f"Saved streaming country: **{_val}**",
        ":material/check:",
    )


_selected_country = st.selectbox(
    "Country",
    options=_country_names,
    index=_country_idx,
    key="settings_country",
    label_visibility="collapsed",
    on_change=_on_country_change,
)
_selected_country_code = _country_code_map.get(_selected_country, DEFAULT_COUNTRY_CODE)

# ============================================================
# STREAMING SUBSCRIPTIONS
# ============================================================

st.subheader("My subscriptions")

# Fetch providers for the saved country
try:
    _providers = get_watch_providers_list(region=_selected_country_code)
    # Sort by country-specific priority (more relevant than global display_priority)
    _providers = sorted(
        _providers,
        key=lambda p: p.get("display_priorities", {}).get(_selected_country_code, 999),
    )[:30]
except requests.RequestException:
    _providers = []

if _providers:
    _provider_id_map = {p["provider_name"]: p["provider_id"] for p in _providers}
    _saved_subs = st.session_state.get("subscriptions", set())

    # Initialize toggle state from saved subscriptions (once per session)
    if "_settings_subs_init" not in st.session_state:
        st.session_state["_settings_selected_subs"] = set(_saved_subs)
        st.session_state["_settings_subs_init"] = True

    _selected_set: set[int] = st.session_state.get("_settings_selected_subs", set())

    def _toggle_provider(pid: int) -> None:
        """Toggle provider and persist to SQLite."""
        s = st.session_state.get("_settings_selected_subs", set())
        if pid in s:
            s.discard(pid)  # Deselect: remove provider from set
        else:
            s.add(pid)      # Select: add provider to set
        st.session_state["_settings_selected_subs"] = s
        # Persist to SQLite (replaces all rows atomically)
        save_subscriptions(list(s), _selected_country_code)
        # Update shared session state so Discover reads the new selection
        st.session_state.subscriptions = set(s)

    # Clickable grid CSS (shared helper with compact gap for provider logos)
    from app.utils import inject_poster_grid_css
    inject_poster_grid_css("provider_grid", gap="0.35rem")

    # Provider logo grid (6 columns)
    _PROVIDER_COLS = 6
    with st.container(key="provider_grid"):
        for row_start in range(0, len(_providers), _PROVIDER_COLS):
            row_providers = _providers[row_start:row_start + _PROVIDER_COLS]
            cols = st.columns(_PROVIDER_COLS)
            for col, p in zip(cols, row_providers):
                pid = p["provider_id"]
                _is_selected = pid in _selected_set
                with col:
                    _logo = poster_url(p.get("logo_path"), size="original")
                    if _logo:
                        # Render all logos as st.html for consistent layout.
                        # Selected logos get a green overlay with checkmark.
                        _overlay = (
                            '<div style="position:absolute;top:0;left:0;width:50px;height:50px;'
                            'background:rgba(33,195,84,0.9);display:flex;align-items:center;'
                            'justify-content:center;color:white;font-size:1.4rem;font-weight:bold;'
                            'border-radius:0.3rem;pointer-events:none">✓</div>'
                            if _is_selected else ''
                        )
                        st.html(
                            f'<div style="position:relative;display:inline-block">'
                            f'<img src="{_logo}" width="50" style="border-radius:0.3rem;display:block">'
                            f'{_overlay}</div>'
                        )
                    st.button(
                        "Toggle",
                        key=f"settings_prov_{pid}",
                        on_click=_toggle_provider,
                        args=(pid,),
                    )

    # Show selected provider names as badges
    _id_to_name = {p["provider_id"]: p["provider_name"] for p in _providers}
    _sel_names = [_id_to_name[pid] for pid in _selected_set if pid in _id_to_name]
    if _sel_names:
        st.markdown(" ".join(f":primary-badge[{n}]" for n in sorted(_sel_names)))
else:
    st.info("Could not load streaming providers.", icon=":material/wifi_off:")

# ============================================================
# PREFERRED LANGUAGE
# ============================================================

st.subheader("Preferred language")

_saved_lang = load_preference("preferred_language")

try:
    _languages = get_languages()
    _lang_names = ["Any"] + sorted(
        {lg["english_name"] for lg in _languages if lg.get("english_name")},
    )
except requests.RequestException:
    _lang_names = ["Any"]

_lang_idx = (
    _lang_names.index(_saved_lang)
    if _saved_lang and _saved_lang in _lang_names else 0
)


def _on_language_change() -> None:
    _val = st.session_state.get("settings_language", "Any")
    if _val == "Any":
        delete_preference("preferred_language")
    else:
        save_preference("preferred_language", _val)
    st.session_state["_settings_toast"] = (
        f"Saved preferred language: **{_val}**",
        ":material/check:",
    )


st.selectbox(
    "Language",
    options=_lang_names,
    index=_lang_idx,
    key="settings_language",
    label_visibility="collapsed",
    on_change=_on_language_change,
)

# ============================================================
# RESET ALL
# ============================================================


def _reset_all() -> None:
    # Country → Switzerland
    save_preference("streaming_country", DEFAULT_COUNTRY_NAME)
    st.session_state["settings_country"] = DEFAULT_COUNTRY_NAME
    # Subscriptions → empty
    save_subscriptions([], DEFAULT_COUNTRY_CODE)
    st.session_state.subscriptions = set()
    st.session_state["_settings_selected_subs"] = set()
    st.session_state.pop("_settings_subs_init", None)
    # Language → Any
    delete_preference("preferred_language")
    st.session_state["settings_language"] = "Any"
    # Toast
    st.session_state["_settings_toast"] = (
        "All settings reset to defaults",
        ":material/restart_alt:",
    )


st.button(
    "Reset to factory settings",
    icon=":material/restart_alt:",
    on_click=_reset_all,
    width="stretch",
)
