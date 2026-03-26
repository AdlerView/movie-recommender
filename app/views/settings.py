"""Settings page — Streaming subscriptions, country, and language preferences.

Manages user preferences that affect Discover page filtering. Saved
preferences persist in SQLite across sessions.

Sections:
- Streaming subscriptions: select providers the user subscribes to
- Streaming country: default region for provider availability
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
from app.utils.tmdb import get_countries, get_languages, get_watch_providers_list

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

# Find index of saved country in the sorted list
_country_idx = (
    _country_names.index(_saved_country)
    if _saved_country in _country_names else 0
)

_selected_country = st.selectbox(
    "Country",
    options=_country_names,
    index=_country_idx,
    key="settings_country",
    label_visibility="collapsed",
)
_selected_country_code = _country_code_map.get(_selected_country, "CH")

# Save / Clear buttons
col_save_c, col_clear_c = st.columns(2)
with col_save_c:
    if st.button("Save country", icon=":material/save:", use_container_width=True):
        save_preference("streaming_country", _selected_country)
        st.session_state["_settings_toast"] = (
            f"Saved streaming country: **{_selected_country}**",
            ":material/check:",
        )
        st.rerun()
with col_clear_c:
    if st.button("Reset to Switzerland", icon=":material/restart_alt:",
                 use_container_width=True):
        save_preference("streaming_country", "Switzerland")
        st.session_state["_settings_toast"] = (
            "Reset streaming country to **Switzerland**",
            ":material/restart_alt:",
        )
        st.rerun()

st.divider()

# ============================================================
# STREAMING SUBSCRIPTIONS
# ============================================================

st.subheader("My subscriptions")
st.caption(
    "Select the streaming providers you subscribe to. "
    "Use 'Only my subscriptions' on the Discover page to filter by these."
)

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
    _provider_names = [p["provider_name"] for p in _providers]
    _provider_id_map = {p["provider_name"]: p["provider_id"] for p in _providers}
    _id_to_name = {p["provider_id"]: p["provider_name"] for p in _providers}

    # Pre-select saved subscriptions
    _saved_subs = st.session_state.get("subscriptions", set())
    _default_names = [
        _id_to_name[pid] for pid in _saved_subs
        if pid in _id_to_name
    ]

    _selected_providers = st.pills(
        "Providers",
        options=_provider_names,
        default=_default_names,
        selection_mode="multi",
        key="settings_providers",
        label_visibility="collapsed",
    )

    # Save / Clear buttons
    col_save_s, col_clear_s = st.columns(2)
    with col_save_s:
        if st.button("Save subscriptions", icon=":material/save:",
                     use_container_width=True):
            _sel_ids = [_provider_id_map[n] for n in (_selected_providers or [])]
            save_subscriptions(_sel_ids, _selected_country_code)
            st.session_state.subscriptions = set(_sel_ids)
            _count = len(_sel_ids)
            st.session_state["_settings_toast"] = (
                f"Saved **{_count}** subscription{'s' if _count != 1 else ''}",
                ":material/check:",
            )
            st.rerun()
    with col_clear_s:
        if st.button("Clear all subscriptions", icon=":material/delete:",
                     use_container_width=True, disabled=not _saved_subs):
            save_subscriptions([], _selected_country_code)
            st.session_state.subscriptions = set()
            st.session_state["_settings_toast"] = (
                "Cleared all subscriptions",
                ":material/delete:",
            )
            st.rerun()
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

_selected_lang = st.selectbox(
    "Language",
    options=_lang_names,
    index=_lang_idx,
    key="settings_language",
    label_visibility="collapsed",
)

col_save_l, col_clear_l = st.columns(2)
with col_save_l:
    if st.button("Save language", icon=":material/save:", use_container_width=True):
        if _selected_lang == "Any":
            delete_preference("preferred_language")
        else:
            save_preference("preferred_language", _selected_lang)
        st.session_state["_settings_toast"] = (
            f"Saved preferred language: **{_selected_lang}**",
            ":material/check:",
        )
        st.rerun()
with col_clear_l:
    if st.button("Reset to Any", icon=":material/restart_alt:",
                 use_container_width=True):
        delete_preference("preferred_language")
        st.session_state["_settings_toast"] = (
            "Reset preferred language to **Any**",
            ":material/restart_alt:",
        )
        st.rerun()
