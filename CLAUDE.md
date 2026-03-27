# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Created:** 2026-03-23
**Updated:** 2026-03-26

---

## Session Startup

At the start of every new session, read ALL of the following files before doing any work:

**Documentation (all `.md` files):**
- `CLAUDE.md`, `README.md`, `docs/TODO.md`, `docs/CONTRIBUTION.md`
- `app/views/VIEWS.md`, `app/utils/UTILS.md`
- `ml/extraction/EXTRACTION.md`
- `ml/classification/CLASSIFICATION.md`
- `ml/scoring/SCORING.md`
- `ml/evaluation/EVALUATION.md`
- `data/input/INPUT.md`, `data/output/OUTPUT.md`
- `docs/archive/ARCHIVE.md`

**Config:**
- `.streamlit/config.toml`

**Source code (all `.py` files):**
- `streamlit_app.py`
- `app/utils/__init__.py`, `app/utils/db.py`, `app/utils/tmdb.py`
- `app/views/discover.py`, `app/views/rate.py`, `app/views/statistics.py`, `app/views/watchlist.py`, `app/views/settings.py`
- `ml/__init__.py`
- `ml/extraction/__init__.py`, `ml/extraction/01_extract_features.py`, `ml/extraction/03_quality_scores.py`, `ml/extraction/04_build_index.py`
- `ml/classification/__init__.py`, `ml/classification/keyword_mood_classifier.py`, `ml/classification/02_predict_moods.py`
- `ml/scoring/__init__.py`, `ml/scoring/user_profile.py`, `ml/scoring/scoring.py`, `ml/scoring/mood_filter.py`
- `ml/evaluation/__init__.py`, `ml/evaluation/ml_eval.py`

---

## Purpose

Movie recommender web app for HSG course 4,125 (Grundlagen und Methoden der Informatik, FS26). Group project worth 20% of final grade. Team of 4: Constantin, Antoine, Dany, Mirko. Deadline: May 14, 2026.

---

## Tech Stack (agent-specific)

Tech stack overview is in README.md. Agent-relevant details only:

- **API key:** `.streamlit/secrets.toml` (gitignored). Use `append_to_response` for combined TMDB calls.
- **SQLite tables:** user_ratings (INTEGER 0-100), user_rating_moods, watchlist, dismissed, user_subscriptions, user_preferences, user_profile_cache, movie_details (scalar metadata + JSON columns: genres, cast_members top 20, crew_members top 20 deduped, countries, keywords). `data/input/tmdb.sqlite` (8.2 GB, 1.17M movies, 30 tables) — offline only.
- **ML signals:** 7 mood categories (TMDB Vibes / Ekman: Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry). Two classification tasks: (1) user preference (liked/disliked), (2) keyword-to-mood. Features: keyword TF-IDF/SVD, genre, director/actor SVD, decade, language, runtime. Mood scores: genre→mood + keyword→mood + overview emotion + review emotion.
- **Runtime data:** Precomputed `.npy` arrays (~3 GB) + TMDB API for live data.

---

## Directory Structure

| Directory | Tracking | Artifact Type |
|-----------|----------|---------------|
| `app/` | Tracked | Streamlit views, utilities, static assets |
| `ml/` | Tracked | ML pipeline by phase (extraction, classification, scoring, evaluation) |
| `data/` | Partial | Pipeline data (input/, output/, user.sqlite) |
| `docs/` | Tracked | Project documentation + planning |
| `.streamlit/` | Partial | Config tracked, secrets gitignored |

**Decision algorithm for new files:**

1. Streamlit views, app utilities → `app/`
2. ML scripts, models, notebooks → `ml/{phase}/`
3. ML-specific documentation → `ml/{phase}/` (co-located with code)
4. Pipeline source data, training data → `data/input/`
5. Pipeline-generated arrays, models, mappings → `data/output/`
6. Project-level documentation → `docs/`
7. Streamlit configuration → `.streamlit/`

```
movie-recommender/
├── streamlit_app.py                        # Entry point (router, init, navigation)
│
├── app/                                    # TRACKED — Streamlit application modules
│   ├── views/                              # Page modules
│   │   ├── VIEWS.md                        # Directory documentation
│   │   ├── discover.py                     # Sidebar filters + poster grid + live filtering
│   │   ├── rate.py                         # Search/browse → rate + mood reactions
│   │   ├── watchlist.py                    # Poster grid → detail dialog + actions
│   │   ├── statistics.py                   # KPIs, charts, ML evaluation, rankings, table
│   │   └── settings.py                     # Subscriptions, streaming country, language prefs
│   ├── utils/                              # App utilities (DB, API)
│   │   ├── UTILS.md                        # Directory documentation (API endpoints, caching, DB schema)
│   │   ├── __init__.py
│   │   ├── db.py                           # SQLite persistence (ratings, watchlist, dismissed, preferences)
│   │   └── tmdb.py                         # TMDB API client (cached)
│
├── static/                                 # Poppins font files (18 TTFs + OFL license)
│
├── ml/                                     # TRACKED — ML pipeline by phase
│   ├── __init__.py
│   ├── extraction/                         # Feature transformation (no ML models)
│   │   ├── EXTRACTION.md                   # Directory documentation (pipeline architecture, stages 1/3/4)
│   │   ├── __init__.py
│   │   ├── 01_extract_features.py          # Stage 1: DB → SVD, onehot, normalized features
│   │   ├── 03_quality_scores.py            # Stage 3: Bayesian average quality scores
│   │   └── 04_build_index.py              # Stage 4: movie_id_index.json + output verification
│   ├── classification/                     # ML models (training + inference)
│   │   ├── CLASSIFICATION.md               # Directory documentation (mood categories, labeling, classifier)
│   │   ├── __init__.py
│   │   ├── keyword_mood_classifier.py      # Keyword → mood: train classifier, infer 70K+
│   │   └── 02_predict_moods.py             # Stage 2: Mood scores per film (4 signals)
│   ├── scoring/                            # Online scoring (runtime, imported by app)
│   │   ├── SCORING.md                      # Directory documentation (scoring + mood filter + sort)
│   │   ├── __init__.py
│   │   ├── user_profile.py                 # User profile vectors from ratings + .npy arrays
│   │   ├── scoring.py                      # 9-signal cosine similarity + dynamic weights
│   │   └── mood_filter.py                  # Local mood filter against mood_scores.npy
│   └── evaluation/                         # Academic ML evaluation
│       ├── EVALUATION.md                   # Directory documentation
│       ├── __init__.py
│       ├── ml_eval.py                      # Shared evaluation functions (classifiers, CV, plots)
│       └── ml_evaluation.ipynb             # NOT YET CREATED — Academic narrative notebook
│
├── data/                                   # PARTIAL — Pipeline data
│   ├── input/                              # Pipeline inputs (sources, training data, rules)
│   │   ├── INPUT.md                        # Directory documentation
│   │   ├── tmdb.sqlite                     # GITIGNORED — Offline TMDB database (8.2 GB)
│   │   ├── tmdb-keyword-frequencies_labeled_top5000.tsv  # tracked — 5K keywords with mood labels
│   │   └── genre_mood_map.json             # tracked — 19 genre → mood rules (hand-crafted)
│   ├── output/                             # Pipeline outputs (feature arrays, models, mappings)
│   │   ├── OUTPUT.md                       # Directory documentation
│   │   ├── keyword_svd_vectors.npy         # GITIGNORED — 1.17M × 200
│   │   ├── director_svd_vectors.npy        # GITIGNORED — 1.17M × 200
│   │   ├── actor_svd_vectors.npy           # GITIGNORED — 1.17M × 200
│   │   ├── keyword_svd.pkl                 # GITIGNORED — Fitted SVD transformer
│   │   ├── director_svd.pkl                # GITIGNORED — Fitted SVD transformer
│   │   ├── actor_svd.pkl                   # GITIGNORED — Fitted SVD transformer
│   │   ├── genre_vectors.npy               # tracked — 1.17M × 19
│   │   ├── decade_vectors.npy              # tracked — 1.17M × 15
│   │   ├── language_vectors.npy            # tracked — 1.17M × 20
│   │   ├── runtime_normalized.npy          # tracked — 1.17M × 1
│   │   ├── mood_scores.npy                 # tracked — 1.17M × 7
│   │   ├── quality_scores.npy              # tracked — 1.17M × 1
│   │   ├── movie_id_index.json             # tracked — movie_id ↔ row_index
│   │   ├── keyword_mood_map.json           # tracked — ~70K keyword → mood predictions
│   │   ├── keyword_classifier_results.csv  # tracked — classifier comparison table
│   │   └── keyword_classifier_confusion_matrix.png  # tracked — confusion matrix plot
│   └── user.sqlite                         # GITIGNORED — App runtime SQLite
│
├── docs/                                   # TRACKED — Project documentation + planning
│   ├── TODO.md                             # Task tracking with deadlines
│   ├── CONTRIBUTION.md                     # Team contribution matrix
│   ├── STREAMLIT_API.yaml                  # Streamlit API reference
│   └── archive/                            # Static/historical artifacts
│       ├── ARCHIVE.md                      # Directory documentation
│       ├── cs-project.md                   # Original project concept
│       ├── prototype-movie-recommender.jpg # UI prototype sketch
│       ├── group-project.pdf               # Course assignment brief
│       ├── 02-exercises.pdf                # Course exercises
│       ├── writing-with-ai.md              # HSG GenAI citation rules
│       ├── TMDB_API.md                     # Full TMDB API reference (archived, 800 lines)
│
├── .streamlit/                             # PARTIAL — Config tracked, secrets gitignored
│   ├── config.toml                         # Cinema Gold theme + fontFaces + server config
│   ├── secrets.toml                        # API keys (gitignored)
│   └── secrets.toml.example                # Template for secrets
│
├── CLAUDE.md                               # Claude Code project instructions
├── README.md                               # Project overview
├── requirements.txt                        # Python dependencies
└── .gitignore
```

---

## Deployment

Public URL: **https://hsg.adlerscope.com** (Cloudflare Tunnel `movie-recommender`).

Setup/run commands are in README.md. Tunnel config paths:
- Config: `~/Developer/.config/cloudflared/config.yml`
- Credentials: `~/Developer/.local/share/cloudflared/movie-recommender.json`
- Cert: `~/Developer/.config/cloudflared/cert.pem` (via `$TUNNEL_ORIGIN_CERT`)

---

## Code Documentation

Code documentation is a grading criterion (Requirement 6, scored 0-3). ALL Python code MUST be thoroughly documented:

- Every function and class MUST have a Google-style docstring
- Module-level docstrings at the top of every `.py` file
- Non-trivial logic MUST have inline comments
- API calls MUST be commented with endpoint and purpose
- Streamlit widget choices MUST be commented with UX rationale

---

## Retrieval + Ranking Architecture

Both Discover and Rate use the same two-layer architecture. Trending endpoints are not used.

**Retrieval Layer (shared, steerable):**
All candidate movies come from `GET /discover/movie` — the same TMDB API endpoint on both pages. Discover passes explicit user-selected filters via `_build_discover_params()`. Rate passes implicit defaults (`sort_by=popularity.desc`, `vote_count.gte=50`). Same endpoint, same caching, same response format.

**Ranking Layer (personalized):**
`score_candidates()` runs whenever a user profile exists. On Discover, the mood filter (`filter_by_mood()`) runs before scoring when mood pills are active. On Rate, no mood filter (no mood pills). Non-personalized sort options on Discover (Popularity, Rating, Release date) skip ML entirely and use the API sort order directly.

**Default = passively personalized:**
"No filters" does not mean "neutral". It means "no manual user overrides, but stored user knowledge is active". When a profile exists, ML scoring always runs. The only true cold start is 0 ratings + no model files — in that case, `discover/movie` popularity order is the fallback.

**Graceful degradation:**
- No `data/output/` → `is_model_available()` returns False → API order used
- No ratings → `get_or_compute_profile()` returns None → API order used
- Model available + ratings exist → full 9-signal personalized scoring

---

## Subdirectory Documentation (mandatory)

Every subdirectory (not root-level) MUST have a Markdown documentation file named after the directory in uppercase: `DIRNAME.md`. This file describes the directory's purpose, contents, and relationships. It is the single entry point for understanding what the directory contains and why.

**Convention:** `<parent>/<dirname>/` → `<parent>/<dirname>/DIRNAME.md`

**Example:** `ml/scoring/` → `ml/scoring/SCORING.md`

**Rules:**
- The file MUST exist before any code is added to the directory
- It MUST describe: purpose, file inventory, data flow, dependencies
- Existing topic-specific .md files (e.g., ML-PIPELINE.md, MOOD.md) MUST be merged into the DIRNAME.md file — one documentation file per directory, not multiple
- SCORING.md is the reference implementation for this convention

**Completed merges (all topic-specific files resolved):**
- `ml/scoring/FILTER.md` → merged into `SCORING.md` + `VIEWS.md` + `UTILS.md` (deleted)
- `ml/classification/MOOD.md` → merged into `CLASSIFICATION.md` (deleted)
- `ml/extraction/ML-PIPELINE.md` → merged into `EXTRACTION.md` + `CLASSIFICATION.md` + `EVALUATION.md` (deleted)
- `app/utils/TMDB_API.md` → used endpoints merged into `UTILS.md`, full reference archived to `docs/archive/`

---

## Key Decisions

**ML approach (2026-03-25):** Personalized recommendations from user ratings + mood reactions. 7 mood categories (Ekman model). Offline pipeline extracts feature vectors from `tmdb.sqlite` into `.npy` arrays. Runtime: cosine similarity between user profile and candidate vectors. Course-compliant ML workflow: train/test split, 5+ classifier comparison, confusion matrix, DummyClassifier baseline.

**Dismiss signal (2026-03-25):** Dismissals ARE negative signals in the contra vector (`ml/scoring/user_profile.py`). Dismissed movies included alongside ratings <= 30. Not used in offline pipeline.

**"Based on your interests" (2026-03-26):** Rate page uses `discover/movie` as candidate source (same retrieval layer as Discover), re-ranked by `score_candidates()`. Falls back to popularity order when no ratings exist.

**Keyword scoring / Discover architecture (2026-03-25):** All filters passed to TMDB API `/discover/movie`. Keyword autocomplete via `search/keyword`. Mood filter + personalized scoring run locally against precomputed `.npy` arrays. `tmdb.sqlite` is offline only.

---

## Conventions

- Streamlit files: no `if __name__ == "__main__"` (whole file runs on every interaction)
- Utility modules: `if __name__ == "__main__"` allowed for quick testing
- Imports: `from app.utils.tmdb import get_genres` (entry point in root enables direct package imports)
- Pages directory: `app/views/` (not `pages/` — conflicts with old Streamlit API)
- State initialization: `st.session_state.setdefault()` in entry point
- UX pattern: Each tab has one responsibility. Poster grids on Discover, Rate, and Watchlist, click → detail dialog overlay (`@st.dialog`). Discover uses `st.sidebar` for filters (only page with sidebar). Settings manages preferences (subscriptions, country, language) that Discover reads from the DB.

### Page Descriptions (current state)

- **Discover:** Sidebar + main layout. Sidebar contains filters (genre, year, runtime, rating, min votes, certification, keywords). Language, streaming country, and providers are managed in Settings (applied automatically via DB preferences). Main page has header, sort dropdown (top-right, default: Personalized), mood pills (toggle-deselect behavior), and poster grid (5 columns, clickable → detail dialog with Watchlist/Dismiss). Live filtering: grid updates on every filter change. "Reset all" in sidebar resets only sidebar filters (not mood/sort). Empty results: info message + "You might also like" fallback grid. Already-rated/dismissed/watchlisted movies excluded. "Load more" button for pagination.
- **Rate:** Pure action tab. TMDB text search + Netflix-style clickable poster grid (personalized via `discover/movie` + ML scoring, or popularity order on cold start). Click → dialog with details, keyword badges, rating slider (0-100 in steps of 10), and 7 mood reaction buttons (see Tech Stack for list). Mood reactions are optional and multi-select, saved alongside the numeric rating. Already-rated movies excluded from browse grid but shown in search results (allows re-rating).
- **Watchlist:** Poster grid of saved movies. Click → dialog with TMDB details, keyword badges, streaming providers (logo images, country from Settings preference). Actions: "Remove from watchlist" or "Mark as watched" (rating slider + mood reaction buttons).
- **Statistics:** KPIs (watch hours, avg runtime, rated/watchlisted/dismissed counts, avg rating), 7 Altair charts (genre, language, decade, rating distribution, rating history, user vs TMDB scatter, mood distribution), top 5 directors + actors rankings, sortable rated movies table. All data from SQLite, zero API calls. PoC — layout polish pending.
- **Settings:** User preferences auto-saved to SQLite on every change. Three sections: (1) Streaming country — dropdown (default: Switzerland), auto-saved on change. (2) My subscriptions — clickable provider logo grid (6 cols, TMDB logos, green checkmark overlay on selected), auto-saved on toggle, selected names shown as `:primary-badge`. (3) Preferred language — dropdown, auto-saved on change. "Reset to factory settings" button at bottom resets all three.

### UI Patterns

- Rating: Slider 0-100 in steps of 10, color-coded track (gray/red/orange/green), dot tick marks at each step, dynamic sentiment label. Save button disabled until slider is moved (prevents accidental 0-ratings). `on_change` callback sets `_*_touched_` flag in session state; flag cleaned up on save.
- TMDB rating display: Always 1 decimal (`:.1f`) across all pages for consistency.
- Dialog pattern: `on_click` sets `_*_selected_id` in session state. Dialog defined inline at trigger point (not top-level decorator) so the movie title becomes the dynamic dialog header. No poster in dialogs (redundant after poster click). Action buttons use `if st.button(): ... st.rerun()` (not `on_click` callbacks — `@st.dialog` inherits from `@st.fragment`, `on_click` only triggers fragment rerun).
- Movie details: Fetched from TMDB API via `append_to_response=credits,videos,watch/providers,release_dates,reviews`. Three specialized renderers in `app/utils/__init__.py`: `render_discover_detail()` (two-column: left=runtime+date, tagline, genre+rating inline, director, overview, streaming logo; right=5 cast photos), `render_watchlist_detail()` (streaming logos, runtime, trailer, Watch Now link), `render_movie_detail_bottom()` (trailer, cast photos, reviews in `st.expander` — each togglable via flags). Discover: full metadata + cast + trailer before buttons + expandable reviews. Rate: title only + rating widget. Watchlist: streaming + trailer + Watch Now + actions. Eagerly cached in user SQLite on every action via `save_movie_details(id, details, keywords=)`.
- Navigation: 5 pages — Discover, Rate, Watchlist (left-aligned), Statistics, Settings (right-aligned via CSS `margin-left: auto`)
- Toolbar: `toolbarMode = "minimal"` hides Streamlit's Deploy button and menu
- Persistence: SQLite load-on-start, save-on-change; session state is runtime source of truth
- Headers: All page headers use `text_alignment="center"`. Section headers use `st.subheader` with `label_visibility="collapsed"` on the associated widget.
- Movie detail badges: Genre = `:gray-badge`, Keywords = `:gray-badge`. Section headers via `st.caption("**Genre**")` etc. Sections only shown when data exists.
- Theme: All colors defined in `.streamlit/config.toml`, NOT in Python files. Dividers use `divider="gray"`, badges use `:gray-badge[...]`. Only exception: functional slider colors (red/orange/green for rating feedback) remain in Python. Streaming providers show TMDB logo images, no brand colors in code.
- Fonts: Poppins (Google Fonts, OFL licensed) served via `enableStaticServing = true` from `static/`. 18 TTF files (weights 100-900, normal + italic) registered as `[[theme.fontFaces]]` in config.toml.

---

## Streamlit DOM Structure (CSS Targeting)

Streamlit does NOT use semantic HTML (`ul/li`, `nav`) for its top navigation. The actual structure:

```
header [data-testid="stHeader"]
  └── div [data-testid="stToolbar"]
        └── div
              └── div (empty spacer)
              └── div.rc-overflow  ← flex container for nav items
                    ├── div.rc-overflow-item (order: 0)  ← Discover
                    ├── div.rc-overflow-item (order: 1)  ← Rate
                    ├── div.rc-overflow-item (order: 2)  ← Watchlist
                    ├── div.rc-overflow-item (order: 3)  ← Statistics
                    ├── div.rc-overflow-item (order: 4)  ← Settings
                    └── div.rc-overflow-item-rest (hidden)
```

Each nav item contains `[data-testid="stTopNavLinkContainer"]` → `a[data-testid="stTopNavLink"]`.

Key selectors:
- Nav container: `[data-testid="stToolbar"] .rc-overflow`
- Nav items: `.rc-overflow > .rc-overflow-item`
- Specific tab: `.rc-overflow > .rc-overflow-item:nth-child(N)`
- Link element: `[data-testid="stTopNavLink"]`

Standard `[data-testid="stNavigation"]` and `ul/li` selectors do NOT work.

### Poster Grid (Rate Page)

Clickable posters use an invisible `st.button` overlaid on `st.image` via CSS. Scoped to `.st-key-poster_grid` (via `st.container(key="poster_grid")`).

```
div[data-testid="stColumn"]           ← position: relative
  ├── div[data-testid="stElementContainer"]  ← image
  │     └── div.stImage → img
  └── div[data-testid="stElementContainer"]  ← button (position: absolute, 100%×100%)
        └── div.stButton → button (opacity: 0)
```

Key gotchas:
- Column testid is `stColumn` (NOT `column`)
- `stElementContainer` may have `width="fit-content"` attribute — must override with explicit `width: 100% !important`
- Use `width/height: 100%` instead of `left: 0; right: 0` for the overlay — the latter doesn't override `fit-content`
- `max-width: 100%` and `padding: 0` needed on the button to prevent Streamlit defaults from shrinking it

### Slider (Rating Dialog)

```
div.stSlider [data-baseweb="slider"]
  └── div                                    ← outer wrapper
        └── div.e16ozfla3                    ← track container (::after for dot ticks)
              ├── div.e16ozfla4              ← thumb container
              │     └── div[role="slider"]   ← draggable thumb
              │           └── div[data-testid="stSliderThumbValue"]  ← value label
              └── div (height: 0.25rem)      ← track bar
  └── div[data-testid="stSliderTickBar"]     ← tick bar below track
        ├── div[data-testid="stMarkdownContainer"]  ← "0.00/10"
        └── div[data-testid="stMarkdownContainer"]  ← "10.00/10"
```

Key gotchas:
- Tick bar testid is `stSliderTickBar` (NOT `stTickBar`, `stTickBarMin`, `stTickBarMax`)
- The tick bar contains only the min/max value labels as `stMarkdownContainer` children — no separate dot elements
- Bottom dots are CSS-generated decorations on `stSliderTickBar` (hide with `background: none`)
- Custom dot ticks use `::after` on `[data-baseweb="slider"] > div` with `radial-gradient` at 10% intervals
- Slider thumb needs `z-index: 2` to stay above the dot tick `::after` layer (`z-index: 1`)

---

## Navigation

- **Parent:** /Users/home/Developer/projects/hsg/cs/CLAUDE.md
