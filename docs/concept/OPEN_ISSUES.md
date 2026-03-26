# Open Issues

> Conceptual gaps, ambiguities, and pending decisions.
> Last updated: 2026-03-25

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
  - Decision (v2, 2026-03-25): Personalized recommendations from user ratings + mood reactions. 7 mood categories (Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry — TMDB Vibes / Ekman model). Users tag moods on Rate page. Offline pipeline extracts feature vectors (keyword/director/actor SVD, genre/decade/language onehot, mood scores, quality scores) from `tmdb.sqlite` into `.npy` arrays. Runtime scoring: cosine similarity between user profile and candidate vectors, mood match, contra-penalty. Full course ML workflow: train/test split, 5+ classifier comparison, confusion matrix, DummyClassifier baseline. See `MIGRATION.md` for full architecture.
  - Superseded: v1 (10 custom mood categories via EmbeddingGemma-300M centroid labeling + KNN, 2026-03-24)
  - Found: 2026-03-18 | Resolved: 2026-03-25

### Medium

- [x] `#017` **[decision]** — Keyword scoring architecture for Discover
  - Context: TMDB keywords follow a long-tail distribution (top keyword "based on novel or book" in ~11% of films). AND logic is impractical — even 2 keywords would eliminate most results.
  - Decision (v2, 2026-03-25): All 14 Discover filters passed to TMDB API `/discover/movie` endpoint (genres, certification, year, language, runtime, score, votes, keywords, providers). Keyword autocomplete via TMDB API `search/keyword`. Mood filter + personalized scoring run locally against precomputed `.npy` arrays. `tmdb.sqlite` is offline only — not queried at runtime. See `MIGRATION.md` for full architecture.
  - Superseded: v1 (keywords.db ~63k movies + 10 mood pill categories, 2026-03-24)
  - Resolved: 2026-03-25

### Low

- [x] `#010` **[unclear]** — "Not interested" signal usage
  - Context: The wireframe has a "not interested" button that skips to the next recommendation. The concept does not specify whether dismissals feed back into the ML model as negative training signals or are just skipped.
  - Decision (2026-03-25): Dismissals ARE negative signals in Layer 2 (online scoring / contra vector). They are NOT used in the offline pipeline (Layer 1). Exact weight contribution to the contra vector is TBD during `scoring.py` implementation. For Phase 0 (DB migration + UI), dismissals remain cosmetic (filtered from results only). Negative signal integration deferred to Phase 2 (online scoring).
  - Found: 2026-03-18 | Resolved: 2026-03-25

- [x] `#011` **[unclear]** — "Based on your stream" data source
  - Context: The wireframe shows a "based on your interests" section with poster-style recommendations. No streaming platform integration is planned.
  - Decision (2026-03-25): "Based on your interests" section on the Rate page, displayed as a poster grid identical to the trending movies layout. Powered by the personalized scoring system (Layer 2). Shows top-N recommended movies based on user's rating history. Requires store/ directory to be populated; falls back to trending when no ratings exist.
  - Found: 2026-03-18 | Resolved: 2026-03-25

## Resolved

- [x] `#001` **[gap]** — SQLite persistence with session state as runtime source (2026-03-23)
- [x] `#003` **[issue]** — Use 19 official TMDB genres directly (2026-03-23)
- [x] `#004` **[decision]** — Movies only, no TV series (2026-03-23)
- [x] `#007` **[decision]** — Rating 0-100 in steps of 10 via slider (2026-03-23, redesigned 2026-03-25 from 0.00-10.00 in 0.01 steps)
- [x] `#009` **[decision]** — Streamlit + server-side TMDB key in `.streamlit/secrets.toml` (2026-03-23)
- [x] `#014` **[decision]** — Multi-page app with top navigation: 4 pages (Discover, Rate, Watchlist, Statistics), entry point `app/streamlit_app.py`, pages in `app/app_pages/` (2026-03-23, restructured 2026-03-24: Watched renamed to Rate as pure action tab)
- [x] `#015` **[decision]** — Card-based UX flow: one movie at a time with rate/dismiss buttons, matching wireframe prototype (2026-03-23)
- [x] `#016` **[decision]** — TMDB API key injected via `_get()` helper in `app/utils/tmdb.py` (2026-03-23)
- [x] `#006` **[decision]** — Sort by `popularity.desc` with `vote_count.gte=100` floor, AND logic for genres, automatic pagination up to 10 pages (2026-03-24)
- [x] `#008` **[gap]** — Flatrate streaming providers (CH) shown on Watchlist with brand-colored badges (2026-03-24)
- [x] `#005` **[gap]** — Statistics data pipeline: normalized SQLite tables (movie_details, movie_genres, movie_cast, movie_crew, movie_countries, movie_keywords), eager fetch on rating save + backfill on startup. Dashboard PoC with KPIs, 7 Altair charts, rankings, rated movies table (2026-03-24)
- [x] `#012` **[gap]** — "No movies found — try selecting fewer tags" message + back button to genre selection (2026-03-24)
