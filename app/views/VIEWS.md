# VIEWS

Streamlit page modules: Discover, Rate, Watchlist, Statistics, Settings.

---

## Shared Patterns

**Retrieval:** Both Discover and Rate use `GET /discover/movie` as candidate source. No trending endpoints. Discover passes explicit sidebar filters; Rate passes defaults (`sort_by=popularity.desc`, `vote_count.gte=50`).

**Ranking:** `score_candidates()` runs whenever a user profile exists. On Discover, mood filter runs before scoring (all sort orders). On Rate, no mood filter. Non-personalized sorts on Discover skip ML entirely.

**Exclusion policy (browse grids):** Rated + dismissed + watchlisted movies are excluded from both Discover and Rate browse grids. Search results on Rate keep rated movies (allows re-rating).

**Dialog pattern:** Poster click sets `_*_selected_id` in session state. `@st.dialog` function called at end of script. Action buttons inside dialogs use `if st.button(): ... st.rerun()` (not `on_click` callbacks — `@st.dialog` inherits from `@st.fragment`, `on_click` only triggers fragment rerun).

**Detail content:** Two shared functions in `app/utils/__init__.py`, used by all three detail dialogs:
- `render_movie_detail_top(details, show_*=True)` — hero section (poster, title, tagline, genre badges, TMDB rating, runtime, release date, director, overview) + streaming providers + Watch Now link. Each section toggleable via keyword args.
- `render_movie_detail_bottom(details, show_*=True)` — trailer embed, cast row (top 5 with photos), user reviews (up to 3). Called after page-specific action buttons.

**Poster grid CSS:** `inject_poster_grid_css(container_key)` from `app/utils/__init__.py` — invisible button overlay on poster images for click interaction. Used by Discover, Rate, Watchlist.

---

## Discover

Sidebar + main page. Only page with a sidebar.

**Sidebar filters:**

| # | Filter | UI Element | TMDB API Parameter |
|---|---|---|---|
| 1 | Genre | `st.pills` multi-select (width-optimized order) | `with_genres` |
| 2 | Release date from | Year input | `primary_release_date.gte` |
| 3 | Release date to | Year input | `primary_release_date.lte` |
| 4 | Runtime | Range slider 0-360 min | `with_runtime.gte/lte` |
| 5 | User score | Range slider 0-10 | `vote_average.gte/lte` |
| 6 | Min user votes | Slider 0-500, default 50 | `vote_count.gte` |
| 7 | Certification | Dropdown (per country) | `certification_country` + `certification.lte` |
| 8 | Keywords | Autocomplete + removable chips | `with_keywords` |
| — | Reset all | Button (resets sidebar only, not mood/sort) | — |

Language, streaming country, and providers are managed in Settings (applied automatically via DB preferences).

**Main page:**

| # | Element | Position |
|---|---|---|
| 1 | Sort dropdown (Personalized, Popularity, Rating, Release date) | Top-right |
| 2 | Mood pills (7 moods, multi-select, toggle-deselect) | Below heading |
| 3 | Poster grid (5 columns, clickable → detail dialog) | Main area |
| 4 | Load more button | Below grid |

**Scoring pipeline (after fetch, before grid):**
1. Mood filter — `filter_by_mood()` for all sort orders when mood pills active
2. ML scoring — `score_candidates()` only for Personalized sort, when profile exists
3. Graceful degradation — no model/no ratings → API popularity order

**Detail dialog actions:** "Not interested" (dismiss + cache details) or "Add to watchlist" (dedup guard + cache details). Both trigger `st.rerun()`.

---

## Rate

Search bar + browse grid. No sidebar.

**Browse grid (no search query):** `discover/movie` with default params, personalized re-ranking when profile exists. Subheader: "Based on your interests" (profile) or "Discover movies" (cold start).

**Search results (query active):** `search/movie` by title. No ML ranking. Rated movies shown (allows re-rating).

**Rating dialog:** 0-100 slider (steps of 10), color-coded track, sentiment label. 7 optional mood reaction buttons. Save button disabled until slider moved. On save: rating + moods persisted, TMDB details + keywords eagerly cached.

---

## Watchlist

Poster grid of saved movies. No sidebar, no search.

**Detail dialog:** TMDB details, keyword badges, streaming providers (user's country, flatrate only, brand-colored). Actions: "Remove from watchlist" or "Mark as watched" (opens rating slider + mood buttons → saves rating, removes from watchlist).

---

## Statistics

Dashboard powered by local SQLite (zero API calls).

- KPIs: watch hours, avg runtime, rated/watchlisted/dismissed counts, avg rating
- 7 Altair charts: genre, language, decade, rating distribution, rating history, user vs TMDB scatter, mood distribution
- Top 5 directors + actors rankings
- Sortable rated movies table with poster thumbnails
- ML Evaluation section: classifier comparison table, best model KPIs, confusion matrix, cross-validation, KNN k-plot

---

## Settings

User preferences persisted in SQLite (`user_preferences` + `user_subscriptions`).

- **Streaming country:** dropdown with save/reset (default: Switzerland). Used by Discover for provider availability.
- **My subscriptions:** provider pills with save/clear. Used by Discover when filtering by "Only my subscriptions".
- **Preferred language:** dropdown with save/reset. Applied as default language filter on Discover.
