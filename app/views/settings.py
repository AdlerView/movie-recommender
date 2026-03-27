"""Settings page — Streaming subscriptions, country, and language preferences.

Manages user preferences that affect Discover page filtering. All changes
are auto-saved to SQLite immediately — no Save/Reset buttons needed.

Sections:
- Streaming country: default region for provider availability
- Streaming subscriptions: select providers the user subscribes to
- Preferred language: default original language filter
"""
from __future__ import annotations

import requests
import streamlit as st
from app.utils.db import (
    delete_preference,
    load_preference,
    save_preference,
    save_subscriptions,
)
from app.utils.tmdb import get_countries, get_languages, get_watch_providers_list, poster_url

st.header("Settings", divider="gray", text_alignment="center")

# --- Deferred toast ---
if "_settings_toast" in st.session_state:
    _msg, _icon = st.session_state.pop("_settings_toast")
    st.toast(_msg, icon=_icon)

# ============================================================
# STREAMING COUNTRY
# ============================================================

st.subheader("Streaming country")
st.caption("Region used for provider availability on the Discover page.")

# Load saved country (default: Switzerland)
_saved_country = load_preference("streaming_country", "Switzerland")

try:
    _countries = get_countries()
    _country_names = sorted(
        {c["english_name"] for c in _countries if c.get("english_name")},
    )
    _country_code_map = {c["english_name"]: c["iso_3166_1"] for c in _countries}
except requests.RequestException:
    _country_names = ["Switzerland"]
    _country_code_map = {"Switzerland": "CH"}

_country_idx = (
    _country_names.index(_saved_country)
    if _saved_country in _country_names else 0
)


def _on_country_change() -> None:
    """Auto-save streaming country when changed."""
    _val = st.session_state.get("settings_country", "Switzerland")
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
_selected_country_code = _country_code_map.get(_selected_country, "CH")

st.divider()

# ============================================================
# STREAMING SUBSCRIPTIONS
# ============================================================

st.subheader("My subscriptions")
st.caption("Select the streaming providers you subscribe to.")

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
        """Toggle a provider and auto-save to DB."""
        s = st.session_state.get("_settings_selected_subs", set())
        if pid in s:
            s.discard(pid)
        else:
            s.add(pid)
        st.session_state["_settings_selected_subs"] = s
        # Auto-save to DB
        save_subscriptions(list(s), _selected_country_code)
        st.session_state.subscriptions = set(s)

    # CSS: compact grid with invisible overlay buttons
    st.html("""<style>
        .st-key-provider_grid [data-testid="stHorizontalBlock"] {
            gap: 0.35rem !important;
        }
        .st-key-provider_grid [data-testid="stColumn"] {
            cursor: pointer !important;
            text-align: center;
            position: relative !important;
            padding: 0.15rem !important;
        }
        .st-key-provider_grid [data-testid="stColumn"] [data-testid="stElementContainer"]:has(.stButton) {
            position: absolute !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 100% !important;
            z-index: 10 !important;
        }
        .st-key-provider_grid [data-testid="stElementContainer"]:has(.stButton) .stButton,
        .st-key-provider_grid [data-testid="stElementContainer"]:has(.stButton) .stButton button {
            width: 100% !important;
            height: 100% !important;
            max-width: 100% !important;
            opacity: 0 !important;
            cursor: pointer !important;
            border: none !important;
            background: transparent !important;
            padding: 0 !important;
        }
        .st-key-provider_grid [data-testid="stColumn"]:hover {
            opacity: 0.85;
            transition: opacity 0.2s;
        }
    </style>""")

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

st.divider()

# ============================================================
# PREFERRED LANGUAGE
# ============================================================

st.subheader("Preferred language")
st.caption("Default original language filter on the Discover page.")

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
    """Auto-save preferred language when changed."""
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

st.divider()

# ============================================================
# RESET ALL
# ============================================================


def _reset_all() -> None:
    """Reset all settings to factory defaults."""
    # Country → Switzerland
    save_preference("streaming_country", "Switzerland")
    st.session_state["settings_country"] = "Switzerland"
    # Subscriptions → empty
    save_subscriptions([], "CH")
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
    use_container_width=True,
)
