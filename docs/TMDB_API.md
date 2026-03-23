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

## Endpoints

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

### Discover Movies

```
GET /3/discover/movie?api_key=KEY&with_genres=28,35&sort_by=vote_average.desc&vote_count.gte=100&page=1
```

The primary endpoint for genre-based recommendations. 30+ filter parameters.

**Key parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `with_genres` | string | Comma-separated genre IDs (AND logic). Use `\|` for OR. |
| `without_genres` | string | Exclude genre IDs |
| `sort_by` | string | Default: `popularity.desc`. Options: `vote_average.desc`, `revenue.desc`, `primary_release_date.desc` |
| `vote_average.gte` | float | Minimum rating (0-10) |
| `vote_count.gte` | float | Minimum vote count (use 100+ to filter obscure films) |
| `primary_release_date.gte` | date | YYYY-MM-DD |
| `primary_release_date.lte` | date | YYYY-MM-DD |
| `with_keywords` | string | Comma-separated keyword IDs |
| `with_watch_providers` | string | Provider IDs (requires `watch_region`) |
| `watch_region` | string | ISO 3166-1 country code (e.g., `CH`, `DE`, `US`) |
| `language` | string | Default: `en-US` |
| `page` | int | 1-500 |

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
GET /3/search/keyword?api_key=KEY&query=dystopia
```

Find keyword IDs by name. Use returned IDs in `discover/movie?with_keywords=`.

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

For the movie recommender, a typical flow uses 2-3 API calls:

1. **Genre list** (once, cache for 1h+): `GET /3/genre/movie/list`
2. **Discover** (per user interaction): `GET /3/discover/movie?with_genres=28&sort_by=vote_average.desc&vote_count.gte=100`
3. **Details** (per movie, with appended data): `GET /3/movie/{id}?append_to_response=credits,watch/providers,videos`

Step 3 returns everything needed for the detail view: runtime, director, cast, streaming availability, and trailer — all in one request.

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
