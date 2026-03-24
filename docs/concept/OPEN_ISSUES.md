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

- [x] `#002` **[gap]** — ML approach unspecified
  - Context: "Implements machine learning" is a project requirement. The concept deferred this to "after the ML class."
  - Decision: Mood classification pipeline (`scripts/mood_classify.py`). Phase 1: Google EmbeddingGemma-300M embeddings (256d) + cosine similarity (threshold 0.85) assigns 909 TMDB keywords to 10 mood categories using 150 curated seed keywords (centroid labeling). Phase 2: sklearn KNeighborsClassifier (k=7, cosine, acc 0.758, F1 0.762) for grading metrics only. Results in `keyword_moods` table in `keywords.db`. Integrated into UI: 10 mood pills on Discover, top 3 mood badges on movie cards via relative scoring.
  - Found: 2026-03-18 | Resolved: 2026-03-24

### Medium

- [x] `#017` **[decision]** — Keyword scoring architecture for Discover
  - Context: TMDB keywords follow a long-tail distribution (top keyword "based on novel or book" in ~11% of films). AND logic is impractical — even 2 keywords would eliminate most results.
  - Decision: Genres = hard AND filter (TMDB API). Keywords/moods = hard relevance filtering via `data/keywords.db`. Films scored by keyword match count, then only movies with score > 0 are shown (sorted by match count DESC, TMDB popularity as tiebreaker). Top 30 popular keywords shown as pills + search popover for all ~34k keywords. 10 mood categories (ML-classified) shown as separate pill section.
  - Database: `keywords.db` is a separate read-only SQLite file generated once via `tmdb-keyword-extract.py` (~63k movies). App opens it as a second connection for scoring queries. Graceful fallback if file missing.
  - Resolved: 2026-03-24

### Low

- [ ] `#010` **[unclear]** — "Not interested" signal usage
  - Context: The wireframe has a "not interested" button that skips to the next recommendation. The concept does not specify whether dismissals feed back into the ML model as negative training signals or are just skipped.
  - Found: 2026-03-18

- [ ] `#011` **[unclear]** — "Based on your stream" data source
  - Context: The wireframe shows a "based on your stream" section with poster thumbnails of watched content. No streaming platform integration is planned. Likely just the in-app rating/watch history, but this is not stated.
  - Found: 2026-03-18

## Resolved

- [x] `#001` **[gap]** — SQLite persistence with session state as runtime source (2026-03-23)
- [x] `#003` **[issue]** — Use 19 official TMDB genres directly (2026-03-23)
- [x] `#004` **[decision]** — Movies only, no TV series (2026-03-23)
- [x] `#007` **[decision]** — Decimal rating 0.00-10.00 via slider in 0.01 steps, matching TMDB scale (2026-03-23)
- [x] `#009` **[decision]** — Streamlit + server-side TMDB key in `.streamlit/secrets.toml` (2026-03-23)
- [x] `#014` **[decision]** — Multi-page app with top navigation: 4 pages (Discover, Rate, Watchlist, Statistics), entry point `app/streamlit_app.py`, pages in `app/app_pages/` (2026-03-23, restructured 2026-03-24: Watched renamed to Rate as pure action tab)
- [x] `#015` **[decision]** — Card-based UX flow: one movie at a time with rate/dismiss buttons, matching wireframe prototype (2026-03-23)
- [x] `#016` **[decision]** — TMDB API key injected via `_get()` helper in `app/utils/tmdb.py` (2026-03-23)
- [x] `#006` **[decision]** — Sort by `popularity.desc` with `vote_count.gte=100` floor, AND logic for genres, automatic pagination up to 10 pages (2026-03-24)
- [x] `#008` **[gap]** — Flatrate streaming providers (CH) shown on Watchlist with brand-colored badges (2026-03-24)
- [x] `#005` **[gap]** — Statistics data pipeline: normalized SQLite tables (movie_details, movie_genres, movie_cast, movie_crew, movie_countries, movie_keywords), eager fetch on rating save + backfill on startup. Dashboard PoC with KPIs, 6 Altair charts, rankings, rated movies table (2026-03-24)
- [x] `#012` **[gap]** — "No movies found — try selecting fewer tags" message + back button to genre selection (2026-03-24)
