# Open Issues

> Conceptual gaps, ambiguities, and pending decisions.
> Last updated: 2026-03-18

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

- [ ] `#001` **[gap]** — No persistence model defined
  - Context: The app needs to store watched films, ratings, and dismissals for the statistics dashboard and ML recommendations. The concept does not address where or how this data is persisted.
  - Found: 2026-03-18

- [ ] `#002` **[gap]** — ML approach unspecified
  - Context: "Implements machine learning" is a project requirement. The concept defers this to "after the ML class." Content-based filtering (user preference vector from rated films → cosine similarity against candidates) is achievable and demonstrable. Collaborative filtering requires multi-user data the app won't have.
  - Found: 2026-03-18

- [ ] `#003` **[issue]** — Custom tags don't match TMDB genres
  - Context: The wireframe proposes tags like "funny", "sad", "independent", "for kids". TMDB has 19 fixed genres (Action, Comedy, Horror, Family, etc.). "Sad" and "independent" have no genre equivalent. "Funny" and "comedy" overlap. Either use TMDB genre names directly, define an explicit mapping table, or use TMDB keywords (`/search/keyword` + `/discover/movie?with_keywords=`) for finer-grained tags.
  - Found: 2026-03-18

- [ ] `#004` **[decision]** — Movies only or movies + TV series
  - Options: Movies only (single API surface: `/discover/movie`, `/movie/{id}`) vs. movies + TV (doubles integration work: separate endpoints, different response fields like `title` vs `name`, `release_date` vs `first_air_date`). The wireframe shows both — TV series in the "based on your stream" section, movies in the recommendation flow.
  - Found: 2026-03-18

### Medium

- [ ] `#005` **[gap]** — Statistics dashboard data pipeline missing
  - Context: The wireframe shows total watch hours, genre counts, favorite director, poster gallery. This requires fetching and caching `runtime`, `genres`, and `credits.crew` (filtered by `job: "Director"`) for every watched film. Can be done in one call per film via `GET /movie/{id}?append_to_response=credits`, but the when/where of caching is unaddressed.
  - Found: 2026-03-18

- [ ] `#006` **[decision]** — Discover result ranking and presentation
  - Options: Sort by TMDB rating (`vote_average.desc` with a `vote_count.gte` floor to exclude obscure films) vs. popularity (`popularity.desc`) vs. random. The wireframe shows single-film presentation — the app needs a pointer into the paginated result set (max 500 pages × 20 results).
  - Found: 2026-03-18

- [ ] `#007` **[decision]** — Rating scale
  - Options: 5 stars (simple, common) vs. 10-point scale (matches TMDB's 0.5–10.0 in 0.5 increments) vs. thumbs up/down (minimal signal). The wireframe shows what looks like a slider or star rating but doesn't specify.
  - Found: 2026-03-18

- [ ] `#008` **[gap]** — Watch provider integration not in concept
  - Context: TMDB provides `GET /movie/{id}/watch/providers` with streaming availability per country (Netflix, Amazon, Disney+, etc.). Showing WHERE to watch a recommended film directly supports the use case. Low implementation effort, high user value. Not mentioned in concept or wireframe.
  - Found: 2026-03-18

- [ ] `#009` **[decision]** — Tech stack undecided
  - Options: The wireframe shows browser windows (web app). No framework, backend, or hosting decisions documented. Key question: does the TMDB API key live in the client (exposed but low risk for a free read-only key) or behind a backend proxy.
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

*No resolved issues yet.*

