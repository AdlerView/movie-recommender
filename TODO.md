# To-Do

> Actionable tasks with owners and deadlines.
> Last updated: 2026-03-25

## In Progress

- [ ] Architecture redesign — personalized recommendations with 14 Discover filters, 7 mood reactions on Rate, ML scoring (Req 4+5)
- [ ] Statistics dashboard polish — improve layout, add chart interactions, refine visual design (Req 3)

## Upcoming

### *Semester Break*

### Week 07 — 2026-04-16 (Coaching: 13.04)

- [ ] Switch to new architecture: TMDB API for filters/discovery, precomputed .npy arrays for scoring, user SQLite for ratings/moods (see MIGRATION.md)
- [ ] Discover: 14 filter controls (genre, mood, certification, year, language, runtime, score, votes, keywords, streaming)
- [ ] Discover: personalized sort option (ML scoring from rating history)
- [ ] Rate: add 7 mood reaction buttons (Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry)
- [ ] Watchlist: add mood reactions to "Mark as watched" dialog
- [ ] DB schema: migrate `ratings` (REAL 0-10) → `user_ratings` (INTEGER 0-100), add `user_rating_moods`, `user_subscriptions`, `user_profile_cache` tables
- [ ] Statistics: add mood distribution chart from user reactions

### Week 08 — 2026-04-23 (Coaching: 20.04)

- [ ] Optional: MVP presentation II
- [ ] Offline pipeline Stage 1: feature extraction (keyword/director/actor TF-IDF → SVD, genre/decade/language onehot)
- [ ] Offline pipeline Stage 2: mood scores per film (genre→mood + keyword→mood mapping + emotion classifier on overview/reviews)
- [ ] Offline pipeline Stage 3: quality scores (Bayesian average)
- [ ] Offline pipeline Stage 4: build numpy index arrays + mappings
- [ ] Online scoring: user profile from ratings → cosine similarity scoring → personalized ranking
- [ ] ML evaluation: train/test split, 5+ classifier comparison, confusion matrix, DummyClassifier baseline, classification_report
- [ ] Statistics dashboard iteration — layout improvements, additional KPIs, chart refinements

### Week 09 — 2026-04-30 (Coaching: 27.04)

- [ ] Finalize contribution matrix (Req 7)

### Week 10 — 2026-05-07 (Coaching: 04.05)

- [ ] Content-based movie recommendations from rated films (if time permits)

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
- [x] Rating system — color-coded track (2026-03-23, redesigned to 0-100 in steps of 10 on 2026-03-25)
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
- [x] Statistics PoC — KPIs, 6 Altair charts, top directors + actors, rated movies table (2026-03-24)
- [x] Cinema Gold theme — dark base, #D4A574 accent, Poppins font, toolbarMode minimal (2026-03-24)
- [x] Keyword scoring on Discover — genre AND + keyword relevance ranking (2026-03-24)
- [x] Keyword badges on movie cards — Genre + Keywords sections on all pages (2026-03-24)
- [x] Centered headers on all pages (2026-03-24)
- [x] Keyword hard-filtering — score 0 movies removed on Discover when keywords active (2026-03-24)
- [x] Keyword search popover — search all keywords via popover on Discover page (2026-03-24)
- [x] Slider save guard — save button disabled until slider moved, prevents accidental 0-ratings (2026-03-24)
- [x] Discover toast feedback — toast notifications for watchlist add and dismiss (2026-03-24)
- [x] Discover filter persistence — pills restored on "Change filters" via saved session state (2026-03-24)
- [x] Discover active filter badges — genre/keyword badges shown on browse phase (2026-03-24)
- [x] Discover movie counter — "Movie X of Y" below action buttons (2026-03-24)
- [x] Discover runtime + streaming — fetch details for current card, show runtime and CH streaming providers (2026-03-24)
- [x] TMDB rating format — unified to 1 decimal across all pages (2026-03-24)
- [x] Re-rating via search — rated movies appear in Rate search results, excluded only from trending (2026-03-24)
- [x] Statistics table fix — proper None handling for TMDB ratings, column width for "Your rating" (2026-03-24)
- [x] Comprehensive TMDB database — tmdb-build-db.py fetches all 1.17M movies with keywords, credits, genres (2026-03-25)
- [x] Doc consistency fixes — normalized all ML stats, removed outdated status block, fixed .gitignore (2026-03-25)

## Superseded

> Tasks from the old 10-category mood classification system (replaced by TMDB Vibes model on 2026-03-25).

- [x] ~~TMDB keyword extraction — keywords.db (~63k movies)~~ → replaced by tmdb.db (1.17M movies)
- [x] ~~Mood classification ML pipeline (EmbeddingGemma-300M + KNN)~~ → replaced by user-rated mood reactions + sklearn classifiers
- [x] ~~Curated mood keywords — 170 seeds in 10 categories~~ → replaced by 7 TMDB Vibes categories
- [x] ~~Mood pills on Discover~~ → mood moved to Rate page; Discover uses keyword/tone search instead
- [x] ~~classify_movie_keywords() for mood badges~~ → mood badges removed; keywords shown directly
