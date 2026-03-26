# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Created:** 2026-03-23
**Updated:** 2026-03-26



---

## Session Startup

At the start of every new session, read ALL of the following files before doing any work:

**Documentation (all `.md` files):**
- `CLAUDE.md`, `README.md`, `docs/TODO.md`, `docs/MIGRATION.md`
- `app/utils/TMDB_API.md`, `docs/CONTRIBUTION.md`, `docs/REQUIREMENTS.md`
- `ml/extraction/ML-PIPELINE.md`, `ml/scoring/FILTER.md`, `ml/classification/MOOD.md`, `ml/scoring/SCORING.md`
- `docs/OPEN_ISSUES.md`, `docs/archive/cs-project.md`

**Config:**
- `.streamlit/config.toml`

**Source code (all `.py` files):**
- `streamlit_app.py`
- `app/utils/__init__.py`, `app/utils/db.py`, `app/utils/tmdb.py`
- `app/views/discover.py`, `app/views/rate.py`, `app/views/statistics.py`, `app/views/watchlist.py`

---

## Purpose

Movie recommender web app for HSG course 4,125 (Grundlagen und Methoden der Informatik, FS26). Group project worth 20% of final grade. Team of 4: Constantin, Antoine, Dany, Mirko. Deadline: May 14, 2026.

---

## Tech Stack

- **Framework:** Streamlit (>=1.53.0)
- **Theme:** "Cinema Gold" — dark base, `#D4A574` gold/copper accent, Poppins font (18 weights via static serving)
- **API:** TMDB API v3 (key in `.streamlit/secrets.toml`, `append_to_response` for combined calls)
- **Database:** SQLite (WAL mode, schema v5 via `PRAGMA user_version`) for user data (user_ratings INTEGER 0-100, user_rating_moods, watchlist, dismissed, user_subscriptions, user_profile_cache). `data/output/tmdb.sqlite` (8.2 GB, 1.17M movies, 30 tables) used offline only for feature extraction. Runtime uses precomputed `.npy` arrays (~3 GB) + TMDB API for live data.
- **ML:** Personalized movie recommendations via scikit-learn. Scoring model uses user ratings + mood reactions as training signal, movie features from `tmdb.sqlite` (keyword TF-IDF/SVD, genre, director/actor SVD, decade, language, runtime). Mood scores per film derived from genre→mood mapping, keyword→mood mapping (supervised pipeline: labeled seed + classifier on sentence embeddings → 70K+ keywords), and emotion classification on overview/review text. 7 mood categories (TMDB Vibes / Ekman model: Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry). Two ML classification tasks: (1) user preference (liked/disliked), (2) keyword-to-mood.
- **Python:** 3.11 (conda environment in `.conda/`)

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
│   │   ├── discover.py                     # Sidebar filters + poster grid + live filtering
│   │   ├── rate.py                         # Search/browse → rate + mood reactions
│   │   ├── watchlist.py                    # Poster grid → detail dialog + actions
│   │   └── statistics.py                   # KPIs, charts, ML evaluation, rankings, table
│   ├── utils/                              # App utilities (DB, API)
│   │   ├── __init__.py
│   │   ├── db.py                           # SQLite persistence (user ratings, watchlist, dismissed)
│   │   ├── tmdb.py                         # TMDB API client (cached)
│   │   └── TMDB_API.md                     # TMDB API endpoint reference
│
├── static/                                 # Poppins font files (18 TTFs + OFL license)
│
├── ml/                                     # TRACKED — ML pipeline by phase
│   ├── __init__.py
│   ├── extraction/                         # Feature transformation (no ML models)
│   │   ├── __init__.py
│   │   ├── 01_extract_features.py          # Stage 1: DB → SVD, onehot, normalized features
│   │   ├── 03_quality_scores.py            # Stage 3: Bayesian average quality scores
│   │   ├── 04_build_index.py              # Stage 4: movie_id_index.json + output verification
│   │   └── ML-PIPELINE.md                  # Pipeline architecture + stages documentation
│   ├── classification/                     # ML models (training + inference)
│   │   ├── __init__.py
│   │   ├── keyword_mood_classifier.py      # Keyword → mood: train classifier, infer 70K+
│   │   ├── 02_predict_moods.py             # Stage 2: Mood scores per film (4 signals)
│   │   └── MOOD.md                         # Keyword-to-mood classification documentation
│   ├── scoring/                            # Online scoring (runtime, imported by app)
│   │   ├── __init__.py
│   │   ├── user_profile.py                 # NOT YET CREATED — User profile from ratings
│   │   ├── scoring.py                      # NOT YET CREATED — 9-signal scoring formula
│   │   ├── filters.py                      # NOT YET CREATED — TMDB API params + mood filter
│   │   ├── SCORING.md                      # Scoring formula + component details
│   │   └── FILTER.md                       # 14 discovery filters documentation
│   └── evaluation/                         # Academic ML evaluation
│       ├── __init__.py
│       ├── ml_eval.py                      # Shared evaluation functions (classifiers, CV, plots)
│       └── ml_evaluation.ipynb             # NOT YET CREATED — Academic narrative notebook
│
├── data/                                   # PARTIAL — Pipeline data
│   ├── input/                              # Pipeline inputs (sources, training data, rules)
│   │   ├── tmdb.sqlite                     # GITIGNORED — Offline TMDB database (8.2 GB)
│   │   ├── tmdb-keyword-frequencies_labeled_top5000.tsv  # tracked — 5K keywords with mood labels
│   │   └── genre_mood_map.json             # tracked — 19 genre → mood rules (hand-crafted)
│   ├── output/                             # Pipeline outputs (feature arrays, models, mappings)
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
│   ├── MIGRATION.md                        # Migration plan + implementation roadmap
│   ├── TODO.md                             # Task tracking with deadlines
│   ├── CONTRIBUTION.md                     # Team contribution matrix
│   ├── REQUIREMENTS.md                     # Grading requirements checklist
│   ├── OPEN_ISSUES.md                     # Conceptual gaps and pending decisions
│   ├── STREAMLIT_API.yaml                  # Streamlit API reference
│   └── archive/                            # Static/historical artifacts
│       ├── cs-project.md                   # Original project concept
│       ├── prototype-movie-recommender.jpg # UI prototype sketch
│       ├── group-project.pdf               # Course assignment brief
│       ├── 02-exercises.pdf                # Course exercises
│       ├── writing-with-ai.md              # HSG GenAI citation rules
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

## Running the App

```bash
conda activate ./.conda
streamlit run streamlit_app.py
```

---

## Deployment

Public URL: **https://hsg.adlerscope.com** (Cloudflare Tunnel)

```bash
# Terminal 2 — start tunnel
cloudflared tunnel --config ~/Developer/.config/cloudflared/config.yml run movie-recommender
```

Tunnel config and credentials follow XDG layout:
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

## Conventions

- Streamlit files: no `if __name__ == "__main__"` (whole file runs on every interaction)
- Utility modules: `if __name__ == "__main__"` allowed for quick testing
- Imports: `from app.utils.tmdb import get_genres` (entry point in root enables direct package imports)
- Pages directory: `app/views/` (not `pages/` — conflicts with old Streamlit API)
- State initialization: `st.session_state.setdefault()` in entry point
- UX pattern: Each tab has one responsibility. Poster grids on Discover, Rate, and Watchlist, click → detail dialog overlay (`@st.dialog`). Discover uses `st.sidebar` for filters (only page with sidebar).

### Page Descriptions (current state)

- **Discover:** Sidebar + main layout. Sidebar contains all filters (genre, year, keywords, runtime, rating, min votes, plus expander for language, certification, streaming). Main page has header, sort dropdown (top-right, default: Personalized), mood pills (toggle-deselect behavior), and poster grid (5 columns, clickable → detail dialog with Watchlist/Dismiss). Live filtering: grid updates on every filter change, no explicit "Discover" button. "Reset all" in sidebar resets only sidebar filters (not mood/sort). Empty results: info message + "You might also like" fallback grid with recommended movies. Already-rated/dismissed/watchlisted movies excluded. "Load more" button for pagination. Provider logos (TMDB `logo_path`) as toggle buttons in streaming filter.
- **Rate:** Pure action tab. TMDB text search + Netflix-style clickable poster grid (trending). Click → dialog with details, keyword badges, rating slider (0-100 in steps of 10), and 7 mood reaction buttons (Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry). Mood reactions are optional and multi-select, saved alongside the numeric rating. Already-rated movies excluded from trending grid but shown in search results (allows re-rating).
- **Watchlist:** Poster grid of saved movies. Click → dialog with TMDB details, keyword badges, streaming providers (CH, flatrate only). Actions: "Remove from watchlist" or "Mark as watched" (rating slider + 7 mood reaction buttons).
- **Statistics:** KPIs (watch hours, avg runtime, rated/watchlisted/dismissed counts, avg rating), 7 Altair charts (genre, language, decade, rating distribution, rating history, user vs TMDB scatter, mood distribution), top 5 directors + actors rankings, sortable rated movies table. All data from SQLite, zero API calls. PoC — layout polish pending.

### UI Patterns

- Rating: Slider 0-100 in steps of 10, color-coded track (gray/red/orange/green), dot tick marks at each step, dynamic sentiment label. Save button disabled until slider is moved (prevents accidental 0-ratings). `on_change` callback sets `_*_touched_` flag in session state; flag cleaned up on save.
- TMDB rating display: Always 1 decimal (`:.1f`) across all pages for consistency.
- Dialog pattern: `on_click` sets `_*_selected_id` in session state, `@st.dialog` function called at end of script (dialogs cannot be triggered from callbacks directly)
- Movie details: Fetched from TMDB API via `append_to_response=credits,videos,watch/providers`. Eagerly cached in user SQLite on rating save.
- Navigation: 4 pages — Discover, Rate, Watchlist (left-aligned), Statistics (right-aligned via CSS)
- Toolbar: `toolbarMode = "minimal"` hides Streamlit's Deploy button and menu
- Persistence: SQLite load-on-start, save-on-change; session state is runtime source of truth
- Headers: All page headers use `text_alignment="center"`. Section headers use `st.subheader` with `label_visibility="collapsed"` on the associated widget.
- Movie detail badges: Genre = `:gray-badge`, Keywords = `:gray-badge`. Section headers via `st.caption("**Genre**")` etc. Sections only shown when data exists.
- Theme: All colors defined in `.streamlit/config.toml`, NOT in Python files. Dividers use `divider="gray"`, badges use `:gray-badge[...]`. Only exception: functional slider colors (red/orange/green for rating feedback) and provider brand colors (Netflix=red etc.) remain in Python.
- Fonts: Poppins (Google Fonts, OFL licensed) served via `enableStaticServing = true` from `static/`. 18 TTF files (weights 100-900, normal + italic) registered as `[[theme.fontFaces]]` in config.toml.

---

## Planned Features (authoritative source: docs/MIGRATION.md)

**All planned features, architecture decisions, scoring formulas, ML pipeline details, and implementation roadmap are defined in [docs/MIGRATION.md](docs/MIGRATION.md).** That file is the single source of truth for all Soll-Zustand. Consult it before implementing any new feature.

Supporting docs (referenced by docs/MIGRATION.md):
- [ml/extraction/ML-PIPELINE.md](ml/extraction/ML-PIPELINE.md) — offline pipeline stages, ML evaluation spec
- [ml/scoring/SCORING.md](ml/scoring/SCORING.md) — scoring formula, dynamic weights, component details
- [ml/scoring/FILTER.md](ml/scoring/FILTER.md) — 14 discovery filters, API parameter mapping, caching
- [ml/classification/MOOD.md](ml/classification/MOOD.md) — keyword-to-mood classification, labeling methodology

**Remaining planned changes** (see docs/MIGRATION.md for full details):
- Online scoring: user profile + 9-signal cosine similarity (Phase 2)
- Discover: personalized sort option via ML scoring (Phase 4.2)
- Rate: "Based on your interests" personalized poster grid (Phase 4.3)
- ML evaluation notebook (Phase 3.3)

**Already completed:**
- Offline pipeline complete (Phase 1a): 4 scripts, 14 outputs in `data/output/` (~4 GB)
- Keyword-to-mood classifier (Phase 1b): MLPClassifier, 68K keyword moods
- Discover page redesign (Phase 4.1): sidebar + 12 filters + poster grid
- ML evaluation on Statistics page (Phase 3.1 + 3.2): classifier table, confusion matrix, CV, KNN k-plot
- Mood reactions on Rate + Watchlist (Phase 0 + 4.4)
- Statistics mood distribution chart (Phase 4.5)

---

## ML Pipeline (completed)

4 offline pipeline scripts produce precomputed feature arrays in `data/output/`.
All idempotent and re-runnable independently.

| Script | Output | Runtime |
|--------|--------|---------|
| `ml/extraction/01_extract_features.py` | 7 `.npy` (keyword/director/actor SVD 200-dim, genre 19-dim, decade 15-dim, language 20-dim, runtime 1-dim) + 3 SVD `.pkl` | 2m39s |
| `ml/classification/02_predict_moods.py` | `mood_scores.npy` (1.17M × 7, 4 signals: genre + keyword + overview emotion + review emotion) | 4h18m |
| `ml/extraction/03_quality_scores.py` | `quality_scores.npy` (Bayesian average, normalized [0,1]) | <1s |
| `ml/extraction/04_build_index.py` | `movie_id_index.json` (1.17M entries) + output verification | <1s |
| `ml/classification/keyword_mood_classifier.py` | `keyword_mood_map.json` (68,462 entries, MLPClassifier val F1=0.76) | 3m |

Run order: `01` + `03` (parallel) → `keyword_mood_classifier` → `02` → `04`

### sklearn Imports Reference

```python
from sklearn.model_selection import train_test_split, KFold, cross_val_score
from sklearn.preprocessing import RobustScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.naive_bayes import GaussianNB
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, ConfusionMatrixDisplay,
)
```

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

## Grading Requirements

| # | Requirement | Status |
|---|------------|--------|
| 1 | Problem statement | Defined |
| 2 | Data via API | TMDB + SQLite integrated |
| 3 | Data visualization | In progress (PoC: KPIs, 7 charts, rankings, table) |
| 4 | User interaction | Implemented (genre discover, rate + mood reactions, dismiss, watchlist, search) |
| 5 | Machine learning | In progress — see [docs/MIGRATION.md](docs/MIGRATION.md) Phase 1-3 |
| 6 | Code documentation | In progress |
| 7 | Contribution matrix | Not started |
| 8 | 4-min video | Not started |

---

## Navigation

- **Parent:** /Users/home/Developer/projects/hsg/cs/CLAUDE.md
