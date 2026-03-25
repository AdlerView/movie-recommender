# TMDB API Reference

> Project-relevant subset of the TMDB API v3 for the movie recommender.
> Full docs: https://developer.themoviedb.org/reference/

---

## Authentication

All requests require the API key. Two options:

```python
# Option 1: Query parameter
params = {"api_key": st.secrets["TMDB_API_KEY"]}
requests.get("https://api.themoviedb.org/3/movie/11", params=params)

# Option 2: Bearer token (preferred)
headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
requests.get("https://api.themoviedb.org/3/movie/11", headers=headers)
```

We use Option 1 (`api_key` query param) since our key type is a v3 API key.

Validate the key:

```
GET /3/authentication?api_key=KEY
→ {"success": true, "status_code": 1, "status_message": "Success."}
```

---

## Rate Limiting

- Legacy limit (40 req/10s) is disabled
- Soft upper limit: ~40 requests/second
- Respect HTTP 429 responses

---

## Image URLs

Images are not returned as full URLs. Build them from three parts:

```
https://image.tmdb.org/t/p/{size}/{file_path}
```

| Size | Width | Use case |
|------|-------|----------|
| `w92` | 92px | Tiny thumbnails |
| `w185` | 185px | List thumbnails |
| `w342` | 342px | Card posters |
| `w500` | 500px | Detail view |
| `w780` | 780px | Large display |
| `original` | Full | High-res |

Example: `poster_path` = `/1E5baAaEse26fej7uHcjOgEE2t2.jpg`

```
https://image.tmdb.org/t/p/w342/1E5baAaEse26fej7uHcjOgEE2t2.jpg
```

---

## append_to_response

Combine multiple sub-requests into one call on any detail endpoint. Comma-separate the values. Max 20 appended requests.

```
GET /3/movie/{id}?append_to_response=credits,videos,watch/providers&api_key=KEY
```

Returns movie details + credits + videos + watch providers in a single response. Each appended result appears as a new top-level key in the JSON.

---

## Pagination

- All list endpoints return paginated results (20 items per page)
- Max 500 pages = 10,000 results
- Use `page` parameter (1-based)
- Response includes `total_pages` and `total_results`

---

## Configuration Endpoints (cached at app startup)

---

### Genre List

```
GET /3/genre/movie/list?language=en&api_key=KEY
```

Returns the 19 official TMDB movie genres.

**Response:**

```json
{
  "genres": [
    {"id": 28, "name": "Action"},
    {"id": 12, "name": "Adventure"},
    {"id": 16, "name": "Animation"},
    {"id": 35, "name": "Comedy"},
    {"id": 80, "name": "Crime"},
    {"id": 99, "name": "Documentary"},
    {"id": 18, "name": "Drama"},
    {"id": 10751, "name": "Family"},
    {"id": 14, "name": "Fantasy"},
    {"id": 36, "name": "History"},
    {"id": 27, "name": "Horror"},
    {"id": 10402, "name": "Music"},
    {"id": 9648, "name": "Mystery"},
    {"id": 10749, "name": "Romance"},
    {"id": 878, "name": "Science Fiction"},
    {"id": 10770, "name": "TV Movie"},
    {"id": 53, "name": "Thriller"},
    {"id": 10752, "name": "War"},
    {"id": 37, "name": "Western"}
  ]
}
```

---

### Certification List

```
GET /3/certification/movie/list?api_key=KEY
```

Returns all supported movie certifications per country.

**Response (excerpt):**

```json
{
  "certifications": {
    "DE": [
      {"certification": "0", "meaning": "No age restriction.", "order": 1},
      {"certification": "6", "meaning": "No children younger than 6 years admitted.", "order": 2},
      {"certification": "12", "meaning": "Children 12 or older admitted, children between 6 and 11 only when accompanied by parent or a legal guardian.", "order": 3},
      {"certification": "16", "meaning": "Children 16 or older admitted, nobody under this age admitted.", "order": 4},
      {"certification": "18", "meaning": "No youth admitted, only adults.", "order": 5}
    ],
    "US": [
      {"certification": "G", "meaning": "All ages admitted.", "order": 1},
      {"certification": "PG", "meaning": "Some material may not be suitable for children under 10.", "order": 2},
      {"certification": "PG-13", "meaning": "Some material may be inappropriate for children under 13.", "order": 3},
      {"certification": "R", "meaning": "Under 17 requires accompanying parent or adult guardian.", "order": 4},
      {"certification": "NC-17", "meaning": "No one 17 and under admitted.", "order": 5}
    ]
  }
}
```

Use `certification_country` + `certification` on the discover endpoint to filter by age rating.

---

### Languages

```
GET /3/configuration/languages?api_key=KEY
```

Returns all ISO 639-1 languages used on TMDB.

**Response (excerpt):**

```json
[
  {"iso_639_1": "en", "english_name": "English", "name": "English"},
  {"iso_639_1": "de", "english_name": "German", "name": "Deutsch"},
  {"iso_639_1": "fr", "english_name": "French", "name": "Français"},
  {"iso_639_1": "ko", "english_name": "Korean", "name": "한국어/조선말"},
  {"iso_639_1": "ja", "english_name": "Japanese", "name": "日本語"}
]
```

Use `iso_639_1` with `with_original_language` on the discover endpoint.

---

### Countries

```
GET /3/configuration/countries?language=en&api_key=KEY
```

Returns all ISO 3166-1 countries. Used for the streaming country
dropdown and certification country selection.

**Response (excerpt):**

```json
[
  {"iso_3166_1": "DE", "english_name": "Germany", "native_name": "Germany"},
  {"iso_3166_1": "US", "english_name": "United States of America", "native_name": "United States"},
  {"iso_3166_1": "CH", "english_name": "Switzerland", "native_name": "Switzerland"}
]
```

---

## Discovery and Search Endpoints

---

### Discover Movies

```
GET /3/discover/movie?api_key=KEY&with_genres=53,18&certification_country=DE&certification.lte=16&with_runtime.gte=90&with_runtime.lte=180&vote_average.gte=6&vote_count.gte=100&with_keywords=10349&watch_region=DE&with_watch_providers=8|337&with_watch_monetization_types=flatrate&sort_by=popularity.desc&page=1
```

The primary endpoint for filtered movie discovery. 30+ filter parameters.

**Key parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `with_genres` | string | Comma-separated genre IDs (AND logic). Use `\|` for OR. |
| `without_genres` | string | Exclude genre IDs |
| `sort_by` | string | Default: `popularity.desc`. Options: `vote_average.desc`, `revenue.desc`, `primary_release_date.desc`, `original_title.asc` |
| `vote_average.gte` | float | Minimum rating (0-10) |
| `vote_average.lte` | float | Maximum rating (0-10) |
| `vote_count.gte` | float | Minimum vote count (use 50+ to filter obscure films) |
| `primary_release_date.gte` | date | YYYY-MM-DD |
| `primary_release_date.lte` | date | YYYY-MM-DD |
| `with_keywords` | string | Comma-separated keyword IDs. Use `\|` for OR, `,` for AND. |
| `without_keywords` | string | Exclude keyword IDs |
| `with_original_language` | string | ISO 639-1 language code (e.g., `en`, `de`, `ko`) |
| `certification_country` | string | ISO 3166-1 code. Required when using `certification` filters. |
| `certification` | string | Exact certification (e.g., `PG-13`, `16`) |
| `certification.lte` | string | Maximum certification (e.g., `16` = show 0, 6, 12, 16) |
| `certification.gte` | string | Minimum certification |
| `with_runtime.gte` | int | Minimum runtime in minutes |
| `with_runtime.lte` | int | Maximum runtime in minutes |
| `with_watch_providers` | string | Provider IDs, pipe-separated for OR (e.g., `8\|337`). Requires `watch_region`. |
| `watch_region` | string | ISO 3166-1 country code (e.g., `DE`, `US`) |
| `with_watch_monetization_types` | string | `flatrate`, `free`, `ads`, `rent`, `buy`. Pipe-separated for OR. Requires `watch_region`. |
| `with_origin_country` | string | ISO 3166-1 origin country |
| `with_cast` | string | Person IDs, comma (AND) or pipe (OR) separated |
| `with_crew` | string | Person IDs, comma (AND) or pipe (OR) separated |
| `with_people` | string | Person IDs (cast or crew), comma (AND) or pipe (OR) separated |
| `with_companies` | string | Company IDs, comma (AND) or pipe (OR) separated |
| `language` | string | Default: `en-US` |
| `page` | int | 1-500 |
| `include_adult` | bool | Default: `false` |

**Response fields per movie:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | TMDB movie ID |
| `title` | string | Localized title |
| `original_title` | string | Original language title |
| `overview` | string | Plot summary |
| `poster_path` | string | Poster image path (append to image base URL) |
| `backdrop_path` | string | Backdrop image path |
| `release_date` | string | YYYY-MM-DD |
| `vote_average` | float | 0-10 rating |
| `vote_count` | int | Number of votes |
| `popularity` | float | TMDB popularity score |
| `genre_ids` | list[int] | Genre IDs (use genre list to resolve names) |
| `original_language` | string | ISO 639-1 |

---

## Movie Detail Endpoints

---

### Movie Details

```
GET /3/movie/{movie_id}?api_key=KEY&append_to_response=credits,watch/providers
```

Full metadata for a single movie.

**Additional fields beyond discover response:**

| Field | Type | Description |
|-------|------|-------------|
| `runtime` | int | Minutes |
| `genres` | list[obj] | `[{"id": 28, "name": "Action"}]` (full objects, not just IDs) |
| `budget` | int | Production budget in USD |
| `revenue` | int | Box office revenue in USD |
| `tagline` | string | Marketing tagline |
| `status` | string | Released, Post Production, etc. |
| `imdb_id` | string | IMDb ID (e.g., `tt0111161`) |
| `homepage` | string | Official website URL |

---

### Movie Release Dates

```
GET /3/movie/{movie_id}/release_dates?api_key=KEY
```

Or via `append_to_response=release_dates` on movie details.

Returns per-country release dates with certification (age rating) and
release type. Used for certification badges on result cards.

**Release types:**

| Type | Meaning |
|------|---------|
| 1 | Premiere |
| 2 | Theatrical (limited) |
| 3 | Theatrical |
| 4 | Digital |
| 5 | Physical |
| 6 | TV |

**Response (excerpt):**

```json
{
  "id": 550,
  "results": [
    {
      "iso_3166_1": "DE",
      "release_dates": [
        {
          "certification": "18",
          "release_date": "1999-11-11T00:00:00.000Z",
          "type": 3
        }
      ]
    },
    {
      "iso_3166_1": "US",
      "release_dates": [
        {
          "certification": "R",
          "release_date": "1999-10-15T00:00:00.000Z",
          "type": 3
        }
      ]
    }
  ]
}
```

To display a certification badge: filter `results` by the user's
country, then pick the entry with `type = 3` (theatrical) or the
first entry with a non-empty `certification`.

---

### Movie Credits

```
GET /3/movie/{movie_id}/credits?api_key=KEY
```

Or via `append_to_response=credits` on movie details.

**Response:**

```json
{
  "id": 550,
  "cast": [
    {
      "id": 819,
      "name": "Edward Norton",
      "character": "The Narrator",
      "order": 0,
      "profile_path": "/path.jpg",
      "popularity": 26.99
    }
  ],
  "crew": [
    {
      "id": 7467,
      "name": "David Fincher",
      "job": "Director",
      "department": "Directing",
      "profile_path": "/path.jpg"
    }
  ]
}
```

Filter crew by `job == "Director"` for the statistics dashboard.

---

### Watch Providers

```
GET /3/movie/{movie_id}/watch/providers?api_key=KEY
```

Or via `append_to_response=watch/providers` on movie details.

**Response:** Keyed by ISO 3166-1 country code.

```json
{
  "results": {
    "CH": {
      "link": "https://www.themoviedb.org/movie/550/watch?locale=CH",
      "flatrate": [
        {"provider_id": 8, "provider_name": "Netflix", "logo_path": "/path.png"}
      ],
      "rent": [...],
      "buy": [...]
    }
  }
}
```

Categories: `flatrate` (subscription), `rent`, `buy`, `free`, `ads`.

---

### Movie Videos

```
GET /3/movie/{movie_id}/videos?api_key=KEY
```

**Response:**

```json
{
  "results": [
    {
      "key": "dQw4w9WgXcQ",
      "site": "YouTube",
      "type": "Trailer",
      "name": "Official Trailer",
      "official": true
    }
  ]
}
```

Build YouTube URL: `https://www.youtube.com/watch?v={key}`

---

### Movie Recommendations

```
GET /3/movie/{movie_id}/recommendations?api_key=KEY&page=1
```

TMDB's own recommendation engine. Returns movies similar to the given one. Same response format as discover. Useful as a fallback or to enrich ML recommendations.

---

### Movie Similar

```
GET /3/movie/{movie_id}/similar?api_key=KEY&page=1
```

Similar movies based on genres and keywords. Same response format as discover.

---

### Search Movie

```
GET /3/search/movie?api_key=KEY&query=inception&page=1
```

Text-based search by title (original, translated, alternative titles).

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | **Required.** Search text. |
| `year` | string | Filter by release year |
| `primary_release_year` | string | Filter by primary release year |
| `language` | string | Default: `en-US` |
| `page` | int | 1-500 |

Same response format as discover.

---

### Search Keyword

```
GET /3/search/keyword?api_key=KEY&query=dystopia&page=1
```

Find keyword IDs by name. Used for the keyword autocomplete field in
the discovery UI. Pass returned IDs to `discover/movie?with_keywords=`.

**Response:**

```json
{
  "results": [
    {"id": 4458, "name": "dystopia"}
  ]
}
```

---

### Trending Movies

```
GET /3/trending/movie/week?api_key=KEY
```

`time_window`: `day` or `week`. Same response format as discover, plus `media_type` field.

---

### Curated Lists

```
GET /3/movie/popular?api_key=KEY&page=1        # By popularity
GET /3/movie/top_rated?api_key=KEY&page=1      # By rating
GET /3/movie/now_playing?api_key=KEY&page=1    # In theatres
GET /3/movie/upcoming?api_key=KEY&page=1       # Coming soon
```

All return the same response format as discover. `now_playing` and `upcoming` also include a `dates` object with `minimum` and `maximum` date strings.

---

### Watch Provider List

```
GET /3/watch/providers/movie?api_key=KEY&watch_region=CH
```

Returns all available streaming providers for a region.

**Response:**

```json
{
  "results": [
    {"provider_id": 8, "provider_name": "Netflix", "logo_path": "/path.png", "display_priority": 1}
  ]
}
```

---

## Recommended Request Pattern

### App startup (5 calls, cached 24h)

```
GET /3/genre/movie/list?language=en
GET /3/configuration/languages
GET /3/certification/movie/list
GET /3/watch/providers/movie?watch_region=DE&language=en
GET /3/configuration/countries?language=en
```

The provider call is re-fetched when the user changes their streaming
country.

### Flow 1: Rate a movie (2 calls)

```
GET /3/search/movie?query={text}&language=en-US&page=1
GET /3/movie/{id}?language=en-US
```

### Flow 2: Discover a movie (~25 calls)

1. **Keyword autocomplete** (debounced 300ms): `GET /3/search/keyword?query={text}&page=1`
2. **Discover** (1-5 pages): `GET /3/discover/movie?with_genres=53,18&certification_country=DE&certification.lte=16&...&page=1`
3. **Details for top-20** (parallel): `GET /3/movie/{id}?append_to_response=watch/providers,videos,release_dates,credits`

Step 3 returns everything needed for the result cards: streaming
providers, trailers, certifications, director + top cast -- all in
one request per movie. 20 parallel calls complete in ~200ms.

Total per discovery: ~25 API calls, ~500ms. Well within the 40 req/s
rate limit.

---

## Error Codes (Common)

| HTTP | Code | Meaning |
|------|------|---------|
| 200 | 1 | Success |
| 401 | 7 | Invalid API key |
| 404 | 34 | Resource not found |
| 422 | 22 | Invalid page (must be 1-500) |
| 429 | 25 | Rate limit exceeded |

---

## Attribution Requirement

TMDB requires attribution for free API use:

> "This product uses the TMDB API but is not endorsed or certified by TMDB."

Use an approved logo from https://www.themoviedb.org/about/logos-attribution in the app's about/credits section.
