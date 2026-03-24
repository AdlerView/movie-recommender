# Open Issues

> Conceptual gaps, ambiguities, and pending decisions.
> Last updated: 2026-03-24

## Legend

| Tag          | Meaning                                          |
|--------------|--------------------------------------------------|
| `[gap]`      | Something not accounted for in the concept       |
| `[issue]`    | Known problem in the current concept draft       |
| `[decision]` | Open decision the group needs to make            |
| `[unclear]`  | Vaguely defined or contradictory                 |

---

## Open

### High

- [ ] `#002` **[gap]** — ML approach unspecified
  - Context: "Implements machine learning" is a project requirement. The concept defers this to "after the ML class." Content-based filtering (user preference vector from rated films → cosine similarity against candidates) is achievable and demonstrable. Collaborative filtering requires multi-user data the app won't have.
  - Found: 2026-03-18

### Medium

- [ ] `#005` **[gap]** — Statistics dashboard data pipeline missing
  - Context: The wireframe shows total watch hours, genre counts, favorite director, poster gallery. This requires fetching and caching `runtime`, `genres`, and `credits.crew` (filtered by `job: "Director"`) for every watched film. Can be done in one call per film via `GET /movie/{id}?append_to_response=credits`, but the when/where of caching is unaddressed.
  - Found: 2026-03-18

- [ ] `#006` **[decision]** — Discover result ranking and presentation
  - Options: Sort by TMDB rating (`vote_average.desc` with a `vote_count.gte` floor to exclude obscure films) vs. popularity (`popularity.desc`) vs. random. The wireframe shows single-film presentation — the app needs a pointer into the paginated result set (max 500 pages × 20 results).
  - Found: 2026-03-18

- [ ] `#008` **[gap]** — Watch provider integration not in concept
  - Context: TMDB provides `GET /movie/{id}/watch/providers` with streaming availability per country (Netflix, Amazon, Disney+, etc.). Showing WHERE to watch a recommended film directly supports the use case. Low implementation effort, high user value. Not mentioned in concept or wireframe.
  - Found: 2026-03-18

### Low

- [ ] `#010` **[unclear]** — "Not interested" signal usage
  - Context: The wireframe has a "not interested" button that skips to the next recommendation. The concept does not specify whether dismissals feed back into the ML model as negative training signals or are just skipped.
  - Found: 2026-03-18

- [ ] `#011` **[unclear]** — "Based on your stream" data source
  - Context: The wireframe shows a "based on your stream" section with poster thumbnails of watched content. No streaming platform integration is planned. Likely just the in-app rating/watch history, but this is not stated.
  - Found: 2026-03-18

- [ ] `#012` **[gap]** — No-results graceful degradation strategy
  - Context: The wireframe correctly includes a "We could not find a movie — please try with less tags" screen. No strategy defined for how to degrade (progressively drop tags, show partial matches, let user deselect manually).
  - Found: 2026-03-18

### Unclear

- [ ] `#013` **[unclear]** — "Unknown" tag purpose
  - Context: The wireframe lists "unknown" as a selectable tag alongside genres. Unclear what this maps to — films without a genre? A random recommendation? A surprise-me feature?
  - Found: 2026-03-18

## Resolved

- [x] `#001` **[gap]** — SQLite persistence with session state as runtime source (2026-03-23)
- [x] `#003` **[issue]** — Use 19 official TMDB genres directly (2026-03-23)
- [x] `#004` **[decision]** — Movies only, no TV series (2026-03-23)
- [x] `#007` **[decision]** — Decimal rating 0.00-10.00 via slider in 0.01 steps, matching TMDB scale (2026-03-23)
- [x] `#009` **[decision]** — Streamlit + server-side TMDB key in `.streamlit/secrets.toml` (2026-03-23)
- [x] `#014` **[decision]** — Multi-page app with top navigation: 4 pages (Discover, Watchlist, Rated, Statistics), entry point `app/streamlit_app.py`, pages in `app/app_pages/` (2026-03-23)
- [x] `#015` **[decision]** — Card-based UX flow: one movie at a time with rate/dismiss buttons, matching wireframe prototype (2026-03-23)
- [x] `#016` **[decision]** — TMDB API key injected via `_get()` helper in `app/utils/tmdb.py` (2026-03-23)
