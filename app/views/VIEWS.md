# VIEWS

Streamlit page modules: Discover, Rate, Watchlist, Statistics, Settings.

---

## Discover Layout

Sidebar + main page. Discover is the only page with a sidebar.

**Sidebar** (collapsible, filter controls):

| # | Filter | UI Element | TMDB API Parameter | Source |
|---|---|---|---|---|
| 1 | Genre | `st.pills` multi-select (width-optimized order) | `with_genres` | `GET /3/genre/movie/list` |
| 2 | Release date from | Year input | `primary_release_date.gte` | -- |
| 3 | Release date to | Year input | `primary_release_date.lte` | -- |
| 4 | Runtime | Range slider 0-360 min | `with_runtime.gte` + `with_runtime.lte` | -- |
| 5 | User score | Range slider 0-10 | `vote_average.gte` + `vote_average.lte` | -- |
| 6 | Min user votes | Slider 0-500, default 50 | `vote_count.gte` | -- |
| 7 | Keywords | Autocomplete (`search/keyword`) + removable chips | `with_keywords` | `GET /3/search/keyword` |
| 8 | Certification | Dropdown (values per country) | `certification_country` + `certification.lte` | `GET /3/certification/movie/list` |
| -- | Reset all | Button (resets sidebar filters only, not mood/sort) | -- | -- |

Language, streaming country, and providers are managed in Settings (applied automatically via DB preferences).

**Main page** (poster grid + mood + sort):

| # | Element | UI Element | Position |
|---|---|---|---|
| 1 | Header | "Which movie will you watch?" | Center |
| 2 | Sort | Dropdown (4 options, default: Personalized) | Right-aligned |
| 3 | Mood | `st.pills` multi-select, toggle-deselect | Below heading |
| 4 | Poster grid | 5 columns, clickable → detail dialog | Main area |
| 5 | Load more | Button | Below grid |

**Interaction model:** Live filtering — every filter/mood/sort change
immediately updates the poster grid. No explicit "Discover" button.

**Genre ordering:** Sorted by label width to maximize sidebar space
(shorter names grouped in same row; longer names get their own row).

**No requirements:** All filters are truly optional — zero filters shows
personalized recommendations (or popularity order on cold start).

---

## Discover Filter Details

---

### Genre

19 toggle buttons loaded from `GET /3/genre/movie/list`.
Optional (no minimum). Multiple genres use AND logic (comma-separated:
`with_genres=53,18`).

| ID | Name | ID | Name |
|---|---|---|---|
| 28 | Action | 10402 | Music |
| 12 | Adventure | 9648 | Mystery |
| 16 | Animation | 10749 | Romance |
| 35 | Comedy | 878 | Science Fiction |
| 80 | Crime | 10770 | TV Movie |
| 99 | Documentary | 53 | Thriller |
| 18 | Drama | 10752 | War |
| 10751 | Family | 37 | Western |
| 14 | Fantasy | 36 | History |
| 27 | Horror | | |

---

### Certification

Toggle buttons whose values change based on the streaming country.
Loaded from `GET /3/certification/movie/list`.

| Country | Values |
|---|---|
| DE | 0, 6, 12, 16, 18 |
| US | G, PG, PG-13, R, NC-17 |
| GB | U, PG, 12A, 15, 18 |
| FR | TP, 12, 16, 18 |

API: `certification_country=DE&certification.lte=16` (uses `order`
field, not numeric value).

---

### Release Date

Two year inputs. API: `primary_release_date.gte=2000-01-01` /
`primary_release_date.lte=2025-12-31`. If only "from" is set, "to"
defaults to today.

---

### Language

Dropdown from `GET /3/configuration/languages`. Shows `english_name`,
sends `iso_639_1`. API: `with_original_language=ko`. Default: all.

---

### Runtime

Range slider 0-360 min. API: `with_runtime.gte=90&with_runtime.lte=180`.
Default: full range.

---

### User Score

Range slider 0.0-10.0. API: `vote_average.gte=6.0&vote_average.lte=10.0`.
Default: full range.

---

### Min User Votes

Single slider 0-500. API: `vote_count.gte=100`. Default: 50 (filters
out obscure movies with unreliable averages).

---

### Keywords

Text field with autocomplete. Each keystroke (debounced 300ms) triggers
`GET /3/search/keyword?query={text}&page=1`. Selected keywords passed to
discover: `with_keywords=10349|285685` (pipe = OR, comma = AND).
Default: OR logic.

---

### Streaming Country

Dropdown from `GET /3/configuration/countries`. Determines which providers
are shown and `watch_region` for the API. Managed in Settings page,
applied automatically.

---

### Streaming Providers

Multi-toggle buttons with provider logos. API:
`watch_region=DE&with_watch_providers=8|337&with_watch_monetization_types=flatrate`.
Managed in Settings page.

---

### Only My Subscriptions

Checkbox. Auto-sets provider filter from `user_subscriptions` table:
`SELECT provider_id FROM user_subscriptions WHERE iso_3166_1 = :country`.
Adds `with_watch_monetization_types=flatrate`.
