# To-Do

> Actionable tasks with owners and deadlines.
> Last updated: 2026-03-24

## In Progress

- [ ] Statistics dashboard polish — improve layout, add chart interactions, refine visual design (Req 3)
- [x] TMDB keyword extraction — `data/keywords.db` (~50k movies) complete
- [x] Mood classification ML pipeline — two-phase: (1) EmbeddingGemma-300M centroid labeling, (2) sklearn KNN classifier → 33,302 keywords in keyword_moods table (Req 5)

## Upcoming

### *Semester Break*

### Week 07 — 2026-04-16 (Coaching: 13.04)

- [x] Discover keyword scoring — `keywords.db` integrated (genre AND filter + keyword/mood relevance ranking)
- [x] Keyword badges on movie cards — three sections (Genre gray, Mood primary, Keywords gray) on all pages
- [x] Centered headers on all pages (Discover, Rate, Watchlist, Statistics)
- [x] Curate mood keyword list — 165 keywords in 10 categories, verified against keywords.db, saved as `data/seed_keywords.json`
- [ ] Mood super-categories in UI — replace individual mood pills with 10 umbrella categories in Discover
- [ ] Statistics dashboard iteration — layout improvements, additional KPIs, chart refinements

### Week 08 — 2026-04-23 (Coaching: 20.04)

- [ ] Optional: MVP presentation II
- [x] mood_classify.py script — Phase 1: EmbeddingGemma-300M centroid labeling (31,941 keywords)
- [x] mood_classify.py script — Phase 2: sklearn KNN classifier (acc 0.622, F1 0.620, 1,361 newly classified)
- [ ] Integrate ML results — read keyword_moods table in db.py, replace MOOD_KEYWORD_NAMES frozenset

### Week 09 — 2026-04-30 (Coaching: 27.04)

- [ ] Finalize contribution matrix (Req 7)

### Week 10 — 2026-05-07 (Coaching: 04.05)

- [ ] Content-based movie recommendations from rated films (if time permits)
- [ ] Decide: use "not interested" as negative ML signal? (Open Issue #010)

### Week 11 — 2026-05-14 (Upload Deadline, Coaching: 11.05)

- [ ] Record 4-minute video with live narration (Req 8)
- [ ] Final code review and documentation pass
- [ ] Upload code + video to Canvas by 23:59

## Backlog

- [ ] "Based on your stream" section — show rated/watchlisted movies as recommendation source (Open Issue #011)

## Done

- [x] Project setup — repo, conda env, requirements.txt, gitignore (2026-03-18)
- [x] Project documentation — REQUIREMENTS.md, CONTRIBUTION.md, OPEN_ISSUES.md (2026-03-18)
- [x] TMDB API integration — genres, trending, discover, movie details, watch providers (2026-03-23)
- [x] SQLite persistence — ratings, watchlist, dismissed with WAL mode (2026-03-23)
- [x] Multi-page app — Discover, Rate, Watchlist, Statistics with top nav (2026-03-23)
- [x] Page restructuring — separate Discover (browse) and Watched (rate) pages, merge Rated into Watched (2026-03-24)
- [x] Watched page — TMDB search, Netflix-style poster grid, integrated Your Ratings section (2026-03-24)
- [x] Rating system — decimal slider 0.00-10.00, color-coded track (2026-03-23)
- [x] Genre selection — two-phase discover flow with 19 TMDB genre pills, AND logic (2026-03-24)
- [x] Automatic pagination — up to 10 pages when current movies exhausted (2026-03-24)
- [x] Discover sorting — popularity.desc with vote_count.gte=100 floor (2026-03-24)
- [x] Watch providers — flatrate streaming badges (CH) on Watchlist with brand colors (2026-03-24)
- [x] Rated page — view and re-rate all rated movies with TMDB metadata fetch (2026-03-23, merged into Watched 2026-03-24)
- [x] Watchlist cleanup — removed user rating display, streaming-only focus (2026-03-24)
- [x] Code documentation — inline comments on all pages and utils (Req 6) (2026-03-24)
- [x] Clickable poster grid — CSS overlay pattern on Rate + Watchlist pages (2026-03-24)
- [x] Dialog-based rating — @st.dialog overlay replaces full-page rating view (2026-03-24)
- [x] Rating slider UX — dot tick marks, sentiment labels, color-coded track (2026-03-24)
- [x] Tab restructuring — Watched -> Rate (pure action), ratings table moved to Statistics (2026-03-24)
- [x] Statistics PoC — KPIs, 6 Altair charts (genre, decade, language, rating distribution, rating history, user vs TMDB), top directors + actors, rated movies table (2026-03-24)
- [x] TMDB keywords infrastructure — separate endpoint, movie_keywords table (schema v4), eager fetch + backfill (2026-03-24)
- [x] Cinema Gold theme — dark base, #D4A574 accent, Poppins font, toolbarMode minimal (2026-03-24)
- [x] Keyword scoring on Discover — genre AND + keyword/mood relevance ranking via keywords.db (2026-03-24)
- [x] Mood badges + keyword sections — Genre/Mood/Keywords badges on Discover, Rate, and Watchlist (2026-03-24)
- [x] Centered headers on all pages (2026-03-24)
- [x] Curated mood keywords — 165 keywords in 10 categories, verified against keywords.db, `data/seed_keywords.json` + `MOOD_KEYWORD_NAMES` in db.py (2026-03-24)
