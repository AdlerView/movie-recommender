# FILTER.md

Discovery filters for the movie recommender. All filters except Mood
are passed directly to the TMDB `discover/movie` API. Mood filtering
runs locally against precomputed model files.

**Created:** 2026-03-26
**Updated:** 2026-03-26

---

## Layout

Sidebar + main page. Discover is the only page with a sidebar.

**Sidebar** (collapsible, filter controls):

| # | Filter | UI Element | TMDB API Parameter | Source |
|---|---|---|---|---|
| 1 | Genre | `st.pills` multi-select (width-optimized order, not alphabetical) | `with_genres` | `GET /3/genre/movie/list` |
| 2 | Release date from | Year input | `primary_release_date.gte` | -- |
| 3 | Release date to | Year input | `primary_release_date.lte` | -- |
| 4 | Runtime | Range slider 0-360 min | `with_runtime.gte` + `with_runtime.lte` | -- |
| 5 | User score | Range slider 0-10 | `vote_average.gte` + `vote_average.lte` | -- |
| 6 | Min user votes | Slider 0-500, default 50 | `vote_count.gte` | -- |
| 7 | Keywords | Autocomplete (`search/keyword`) + removable chips | `with_keywords` | `GET /3/search/keyword` |
| -- | *More filters (expander)* | | | |
| 8 | Language | Dropdown | `with_original_language` | `GET /3/configuration/languages` |
| 9 | Certification | Dropdown (values per country) | `certification_country` + `certification.lte` | `GET /3/certification/movie/list` |
| 10 | Streaming country | Dropdown | `watch_region` | `GET /3/configuration/countries` |
| 11 | Streaming providers | Toggle buttons with provider logos (TMDB `logo_path`, ~30px) | `with_watch_providers` | `GET /3/watch/providers/movie` |
| 12 | Only my subscriptions | Checkbox | `with_watch_providers` (filtered) | Local `user_subscriptions` DB |
| -- | Reset all | Button (resets sidebar filters only, not mood/sort) | -- | -- |

**Main page** (poster grid + mood + sort):

| # | Element | UI Element | Position |
|---|---|---|---|
| 1 | Header | "Which movie will you watch?" | Center |
| 2 | Sort | Dropdown (4 options, default: Personalized) | Right-aligned, same line as "Recommended Movies" |
| 3 | Mood | `st.pills` multi-select, toggle-deselect | Below heading, above grid |
| 4 | Poster grid | 5 columns, clickable → detail dialog | Main area |
| 5 | Load more | Button | Below grid |

**Interaction model:** Live filtering — every filter/mood/sort change
immediately updates the poster grid. No explicit "Discover" button.

**Genre ordering:** Not alphabetical. Sorted by label width to maximize
sidebar space usage (shorter names like War, Crime, Music grouped in
same row; longer names like Science Fiction get their own row).

**No requirements:** Genre has no minimum selection. Mood has no
"optional" label. All filters are truly optional — zero filters shows
personalized recommendations (or popularity order on cold start).

---

## Filter Details

---

### Mood (local, not TMDB API)

7 toggle buttons: Happy, Interested, Surprised, Sad, Disgusted,
Afraid, Angry. Multi-select.

This is the only filter that runs locally. The TMDB API has no mood
concept. After the API returns candidates, each candidate's mood
scores are looked up from `mood_scores.npy` and filtered:

```python
threshold = 0.3
keep = [m for m in candidates if mood_scores[m][selected_mood] > threshold]

# Fallback for rare moods: lower threshold stepwise
for t in [0.2, 0.1, 0.0]:
    if len(keep) >= 20:
        break
    threshold = t
    keep = [m for m in candidates if mood_scores[m][selected_mood] > threshold]
```

If no mood is selected, no mood filtering occurs. The implicit mood
from the user's rating history still influences the personalized
scoring (see SCORING.md).

---

### Sort

Dropdown with 4 options:

| Option | TMDB `sort_by` | ML Scoring |
|---|---|---|
| Personalized Score (default) | `popularity.desc` | Yes (full scoring) |
| Popularity | `popularity.desc` | No |
| Rating | `vote_average.desc` | No |
| Release Date | `primary_release_date.desc` | No |

For "Personalized Score", the API sorts by popularity (to get a
reasonable candidate pool), then the local scoring pipeline re-ranks
the results. For all other options, the API sort order is final --
only mood filtering is applied locally.

---

### Genre

19 toggle buttons loaded from `GET /3/genre/movie/list`.

Optional (no minimum). Multiple genres use AND logic (comma-separated
in the API: `with_genres=53,18`).

Full genre list:

| ID | Name |
|---|---|
| 28 | Action |
| 12 | Adventure |
| 16 | Animation |
| 35 | Comedy |
| 80 | Crime |
| 99 | Documentary |
| 18 | Drama |
| 10751 | Family |
| 14 | Fantasy |
| 36 | History |
| 27 | Horror |
| 10402 | Music |
| 9648 | Mystery |
| 10749 | Romance |
| 878 | Science Fiction |
| 10770 | TV Movie |
| 53 | Thriller |
| 10752 | War |
| 37 | Western |

---

### Certification

Toggle buttons whose values change based on the selected streaming
country. Loaded from `GET /3/certification/movie/list`.

Examples:

| Country | Values |
|---|---|
| DE | 0, 6, 12, 16, 18 |
| US | G, PG, PG-13, R, NC-17 |
| GB | U, PG, 12A, 15, 18 |
| FR | TP, 12, 16, 18 |

API parameters:

```
certification_country=DE
certification.lte=16          # shows 0, 6, 12, 16
```

The `.lte` (less than or equal) parameter uses the `order` field from
the certification list, not the numeric value. So `certification.lte=16`
in Germany means order <= 4 (which includes 0, 6, 12, 16).

---

### Release Date

Two year inputs: "from" and "to".

API parameters:

```
primary_release_date.gte=2000-01-01
primary_release_date.lte=2025-12-31
```

If only "from" is set, "to" defaults to today. If only "to" is set,
"from" is omitted (no lower bound).

---

### Language

Dropdown loaded from `GET /3/configuration/languages`. Shows
`english_name` to the user, sends `iso_639_1` to the API.

API parameter:

```
with_original_language=ko
```

Default: all languages (parameter omitted).

---

### Runtime

Range slider with two handles, 0 to 360 minutes.

API parameters:

```
with_runtime.gte=90
with_runtime.lte=180
```

Default: full range (parameters omitted).

---

### User Score

Range slider with two handles, 0.0 to 10.0.

API parameters:

```
vote_average.gte=6.0
vote_average.lte=10.0
```

Default: full range (parameters omitted).

---

### Min User Votes

Single slider, 0 to 500.

API parameter:

```
vote_count.gte=100
```

Default: 50. This filters out obscure movies with very few ratings,
which tend to have unreliable vote averages.

---

### Keywords

Text field with autocomplete. Each keystroke (debounced 300ms) triggers:

```
GET /3/search/keyword?query={text}&page=1
```

Returns keyword IDs and names. Selected keywords are passed to
discover:

```
with_keywords=10349|285685       # pipe = OR logic
with_keywords=10349,285685       # comma = AND logic
```

Default behavior: OR logic (any of the selected keywords).

---

### Streaming Country

Dropdown loaded from `GET /3/configuration/countries`. Determines
which streaming providers are shown and which watch region the API
uses.

When changed, the provider list is re-fetched:

```
GET /3/watch/providers/movie?watch_region=DE&language=en
```

Default: user's locale or DE.

---

### Streaming Providers

Multi-toggle buttons loaded from the watch providers API (filtered by
selected country). Shows provider logos.

API parameters:

```
watch_region=DE
with_watch_providers=8|337                     # Netflix OR Disney+
with_watch_monetization_types=flatrate         # subscription only
```

Pipe-separated for OR logic. The `monetization_types` parameter
controls whether to include rent/buy options or only subscriptions.

---

### Only My Subscriptions

Checkbox. When checked, the provider filter is automatically set to
the user's saved subscriptions from `user_subscriptions` table:

```sql
SELECT provider_id FROM user_subscriptions
WHERE iso_3166_1 = :selected_country
```

This pre-selects the provider toggles and adds
`with_watch_monetization_types=flatrate` to the API call.

---

## API Call Construction

All filters are combined into a single `discover/movie` call:

```
GET /3/discover/movie
    ?with_genres=53,18
    &certification_country=DE
    &certification.lte=16
    &primary_release_date.gte=2000-01-01
    &primary_release_date.lte=2025-12-31
    &with_original_language=en
    &with_runtime.gte=90
    &with_runtime.lte=180
    &vote_average.gte=6
    &vote_count.gte=100
    &with_keywords=10349
    &watch_region=DE
    &with_watch_providers=8|337
    &with_watch_monetization_types=flatrate
    &sort_by=popularity.desc
    &page=1
```

Optional parameters are only included when the user has set them.
The API ignores absent parameters (no filtering on that dimension).

Already-rated movies are excluded locally after the API returns
results (the TMDB API has no parameter for this).

---

## Caching Strategy

### Configuration (app startup, rarely changes)

| Call | Cache Key | TTL |
|---|---|---|
| `configuration` | `config` | 24h |
| `genre/movie/list` | `genres` | 24h |
| `configuration/languages` | `languages` | 24h |
| `certification/movie/list` | `certifications` | 24h |
| `configuration/countries` | `countries` | 24h |
| `watch/providers/movie?watch_region=XX` | `providers_{country}` | 24h + on country change |
| `watch/providers/regions` | `provider_regions` | 24h |

### Per-request (changes frequently)

| Call | Cache Key | TTL | Rationale |
|---|---|---|---|
| `discover/movie?...` | filter params + page | 10m | Bounded key space (genre combos) |
| `search/movie?query=...` | `search_{query}_{page}` | 5m | Unbounded key space (free text) |
| `search/keyword?query=...` | `kw_{query}` | 5m | Unbounded key space (free text) |

### Per-movie (stable data, fetched on demand)

| Call | Cache Key | TTL | Rationale |
|---|---|---|---|
| `movie/{id}` (details) | `movie_{id}` | 1h | Votes change slowly |
| `movie/{id}/keywords` | `keywords_{id}` | 24h | Keywords rarely change |
| `movie/{id}/watch/providers` | `providers_{id}_{region}` | 1h | Licensing changes weekly |
