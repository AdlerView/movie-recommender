# To-Do

> Actionable tasks with owners and deadlines.
> Last updated: 2026-03-26
>
> **Rule:** When a task is checked off (`[x]`), it MUST be moved to the **Done** section (with completion date) or **Superseded** section (with replacement note). Completed tasks MUST NOT remain in In Progress, Upcoming, or Backlog.

## In Progress

- [ ] Architecture redesign — personalized recommendations with 14 Discover filters, 7 mood reactions on Rate, ML scoring (Req 4+5) *(Discover sidebar + 12 filters + poster grid done; ML scoring pending Phase 2)*
- [ ] Statistics dashboard polish — improve layout, add chart interactions, refine visual design (Req 3)
- [ ] Discover page visual polish — layout refinements, spacing, visual consistency pass

## Upcoming

- [ ] Online scoring: user profile from ratings → cosine similarity scoring → personalized ranking (Phase 2)
- [ ] Discover: personalized sort option (ML scoring from rating history, Phase 4.2)
- [ ] Rate: "Based on your interests" personalized poster grid (Phase 4.3)
- [ ] ML evaluation notebook — ml/evaluation/ml_evaluation.ipynb (academic narrative, Phase 3.3)
- [ ] Statistics dashboard polish — layout improvements, chart refinements (Req 3)
- [ ] Discover page visual polish — layout refinements, spacing
- [ ] Finalize contribution matrix (Req 7)
- [ ] Record 4-minute video with live narration (Req 8)
- [ ] Final code review and documentation pass (Req 6)
- [ ] Content-based movie recommendations from rated films (if time permits)
- [ ] Upload code + video to Canvas by 2026-05-14 23:59

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
- [x] Statistics PoC — KPIs, 7 Altair charts, top directors + actors, rated movies table (2026-03-24)
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
- [x] Phase 1 cleanup — removed old keyword/mood pipeline code from all app files (db.py, discover.py, rate.py, watchlist.py, streamlit_app.py), app functional with genre-only discovery (2026-03-26)
- [x] DB schema v5 — migrate `ratings` (REAL 0-10) → `user_ratings` (INTEGER 0-100), add `user_rating_moods`, `user_subscriptions`, `user_profile_cache` tables (2026-03-26)
- [x] Rate: 7 mood reaction buttons (Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry) on rating dialog (2026-03-26)
- [x] Keyword seed dataset — 5,000 keywords labeled + reviewed (1,049 single-label, 1,634 multi, 2,317 none — see docs/MOOD.md) (2026-03-26)
- [x] Genre-to-mood mapping — 19 TMDB genres with hand-crafted mood weights in `data/output/genre_mood_map.json` (2026-03-26)
- [x] Keyword-to-mood classifier — `ml/classification/keyword_mood_classifier.py`: 80/10/10 split, scaled+unscaled, 5+ classifiers (MLPClassifier best, val F1=0.76, test acc=78%), inferred 65,779 keywords → `data/output/keyword_mood_map.json` (68,462 entries, 3.0 MB) (2026-03-26)
- [x] Directory restructuring — `data/` + `model/` → `data/` (tracked: labeled/, evaluation/) + `data/output/` (gitignored: DBs, .npy, .pkl, generated JSON). Gitignore simplified to single `data/output/` rule (2026-03-26)
- [x] Feature extraction pipeline — `ml/extraction/01_extract_features.py`: 7 features from tmdb.sqlite (keyword/director/actor SVD 200-dim, genre 19-dim, decade 15-dim, language 20-dim, runtime 1-dim), 3 SVD .pkl models. Total: ~2.9 GB in data/output/. Runtime: 2m39s (2026-03-26)
- [x] Quality scores pipeline — `ml/extraction/03_quality_scores.py`: Bayesian average on vote_average + vote_count (m=3.0, C=5.90), normalized to [0,1]. Spot checks: Fight Club 0.83, Pulp Fiction 0.84, Dark Knight 0.84. 4.5 MB (2026-03-26)
- [x] Discover page redesign — sidebar with 12 filters (genre, year, runtime, rating, min votes, keywords, language, certification, streaming providers), main page with mood pills, sort dropdown, poster grid (5 cols), detail dialog, live filtering, load more, empty-state fallback. New TMDB API functions in tmdb.py. Visual polish pending. (2026-03-26)
- [x] ML Evaluation utility + Statistics section — `app/utils/ml_eval.py` (4 generic functions: evaluate_classifiers, best_model_report, run_cross_validation, knn_hyperparameter_plot). Statistics page: classifier comparison table, best model KPIs (MLPClassifier 89% val acc, 0.76 F1), confusion matrix, 10-fold CV (81.6% ± 3.8%), KNN k=1..20 plot. All course requirements (Req 5) visible. (2026-03-26)
- [x] Mood prediction pipeline — `ml/classification/02_predict_moods.py`: 4 signals (genre, keyword, overview emotion, review emotion) with dynamic weighting. 996K overviews + 23K reviews classified (distilroberta, 4h18min). Coverage: 94.6% (1.11M/1.17M). mood_scores.npy 31.4 MB. (2026-03-26)
- [x] Build index pipeline — `ml/extraction/04_build_index.py`: movie_id_index.json (1.17M entries, 18.4 MB), all 14 pipeline outputs verified. Phase 1a complete. (2026-03-26)
- [x] Watchlist: mood reactions in "Mark as watched" dialog — rating slider + 7 mood buttons, saves to user_rating_moods (2026-03-26)
- [x] Statistics: mood distribution chart from user reactions — Altair horizontal bar chart from load_mood_distribution() (2026-03-26)

## Superseded

> Tasks from the old 10-category mood classification system (replaced by TMDB Vibes model on 2026-03-25).

- [x] ~~TMDB keyword extraction — keywords.db (~63k movies)~~ → replaced by tmdb.sqlite (1.17M movies)
- [x] ~~Mood classification ML pipeline (EmbeddingGemma-300M + KNN)~~ → replaced by user-rated mood reactions + sklearn classifiers
- [x] ~~Curated mood keywords — 170 seeds in 10 categories~~ → replaced by 7 TMDB Vibes categories
- [x] ~~Mood pills on Discover~~ → mood moved to Rate page; Discover uses keyword/tone search instead
- [x] ~~classify_movie_keywords() for mood badges~~ → mood badges removed; keywords shown directly
