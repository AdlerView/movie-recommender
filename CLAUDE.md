# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Created:** 2026-03-23
**Updated:** 2026-03-26



---

## Session Startup

At the start of every new session, read ALL of the following files before doing any work:

**Documentation (all `.md` files):**
- `CLAUDE.md`, `README.md`, `TODO.md`, `MIGRATION.md`
- `docs/TMDB_API.md`, `docs/CONTRIBUTION.md`, `docs/REQUIREMENTS.md`
- `docs/tmdb-schema.mmd`, `docs/ML-PIPELINE.md`, `docs/FILTER.md`, `docs/MOOD.md`, `docs/SCORING.md`
- `docs/concept/cs-project.md`, `docs/concept/OPEN_ISSUES.md`, `docs/concept/prototype-movie-recommender.jpg`

**Config:**
- `.streamlit/config.toml`

**Source code (all `.py` files):**
- `app/streamlit_app.py`
- `app/utils/__init__.py`, `app/utils/db.py`, `app/utils/tmdb.py`
- `app/app_pages/discover.py`, `app/app_pages/rate.py`, `app/app_pages/statistics.py`, `app/app_pages/watchlist.py`

---

## Purpose

Movie recommender web app for HSG course 4,125 (Grundlagen und Methoden der Informatik, FS26). Group project worth 20% of final grade. Team of 4: Constantin, Antoine, Dany, Mirko. Deadline: May 14, 2026.

---

## Tech Stack

- **Framework:** Streamlit (>=1.53.0)
- **Theme:** "Cinema Gold" — dark base, `#D4A574` gold/copper accent, Poppins font (18 weights via static serving)
- **API:** TMDB API v3 (key in `.streamlit/secrets.toml`, `append_to_response` for combined calls)
- **Database:** SQLite (WAL mode, schema v5 via `PRAGMA user_version`) for user data (user_ratings INTEGER 0-100, user_rating_moods, watchlist, dismissed, user_subscriptions, user_profile_cache). `data/tmdb.db` (8.2 GB, 1.17M movies, 30 tables) used offline only for feature extraction. Runtime uses precomputed `.npy` arrays (~3 GB) + TMDB API for live data.
- **ML:** Personalized movie recommendations via scikit-learn. Scoring model uses user ratings + mood reactions as training signal, movie features from `tmdb.db` (keyword TF-IDF/SVD, genre, director/actor SVD, decade, language, runtime). Mood scores per film derived from genre→mood mapping, keyword→mood mapping (supervised pipeline: labeled seed + classifier on sentence embeddings → 70K+ keywords), and emotion classification on overview/review text. 7 mood categories (TMDB Vibes / Ekman model: Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry). Two ML classification tasks: (1) user preference (liked/disliked), (2) keyword-to-mood.
- **Python:** 3.11 (conda environment in `.conda/`)

---

## Directory Structure

Each directory has exactly one tracking status and one artifact type.
No gitignore exceptions needed.

| Directory | Tracking | Artifact Type |
|-----------|----------|---------------|
| `app/` | Tracked | Runtime application code |
| `pipeline/` | Tracked | Offline pipeline scripts |
| `data/` | Tracked | Curated input data + evaluation results |
| `store/` | Gitignored | All large, generated, and runtime files |
| `notebooks/` | Tracked | Jupyter notebooks |
| `docs/` | Tracked | Project documentation |
| `.streamlit/` | Partial | Config tracked, secrets gitignored |

**Decision algorithm for new files:**

1. Code (`*.py`, `*.ipynb`) → `app/`, `pipeline/`, or `notebooks/`
2. Documentation (`*.md`, `*.mmd`) → `docs/`
3. Manually curated and < 5 MB → `data/labeled/`
4. Pipeline evaluation result and < 5 MB → `data/evaluation/`
5. Generated, > 5 MB, or database → `store/`
6. Streamlit configuration → `.streamlit/`

```
movie-recommender/
├── app/                                    # TRACKED — Runtime application
│   ├── streamlit_app.py                    # Entry point (router, init, navigation)
│   ├── app_pages/                          # Page modules
│   │   ├── discover.py                     # 14 filters + personalized scoring
│   │   ├── rate.py                         # Search/browse → rate + mood reactions
│   │   ├── watchlist.py                    # Poster grid → detail dialog + actions
│   │   └── statistics.py                   # KPIs, charts, rankings, table
│   ├── utils/                              # Business logic & helpers
│   │   ├── __init__.py
│   │   ├── db.py                           # SQLite persistence (user ratings, watchlist, dismissed)
│   │   ├── tmdb.py                         # TMDB API client (cached)
│   │   ├── scoring.py                      # Scoring formula + dynamic weights
│   │   ├── filters.py                      # TMDB API parameter builder + local mood filter
│   │   ├── user_profile.py                 # User profile computation from ratings
│   │   └── ml_eval.py                      # Shared ML evaluation (classifiers, metrics, CV)
│   └── static/                             # Poppins font files (18 TTFs + OFL license)
│
├── pipeline/                               # TRACKED — Offline pipeline scripts
│   ├── keyword_mood_classifier.py          # Keyword → mood: train classifier, infer 70K+
│   ├── 01_extract_features.py              # Stage 1: DB → feature matrices (SVD, onehot)
│   ├── 02_predict_moods.py                 # Stage 2: Mood scores per film (4 signals)
│   ├── 03_quality_scores.py                # Stage 3: Bayesian average quality scores
│   └── 04_build_index.py                   # Stage 4: Save numpy arrays + mappings
│
├── data/                                   # TRACKED — Curated input data + evaluation results
│   ├── labeled/                            # Manually curated training data
│   │   ├── tmdb-keyword-frequencies.tsv    # 70K keyword frequency export from tmdb.db
│   │   └── tmdb-keyword-frequencies_labeled_top5000.tsv  # 5K keywords with mood labels
│   └── evaluation/                         # Pipeline evaluation outputs (small, reproducible)
│       ├── keyword_classifier_results.csv  # Classifier comparison table (scaled + unscaled)
│       └── keyword_classifier_confusion_matrix.png  # Best model confusion matrix
│
├── store/                                  # GITIGNORED — All large/generated/runtime files
│   ├── tmdb.db                             # Offline TMDB database (8.2 GB, 1.17M movies, 30 tables)
│   ├── exports/                            # TMDB daily ID exports (source for tmdb.db)
│   ├── movies.db                           # App runtime SQLite (user ratings, watchlist, dismissed)
│   ├── genre_mood_map.json                 # 19 genre → mood rules (hand-crafted)
│   ├── keyword_svd_vectors.npy             # 1.17M × 200, generated by Stage 1
│   ├── director_svd_vectors.npy            # 1.17M × 200, generated by Stage 1
│   ├── actor_svd_vectors.npy               # 1.17M × 200, generated by Stage 1
│   ├── genre_vectors.npy                   # 1.17M × 19, generated by Stage 1
│   ├── decade_vectors.npy                  # 1.17M × 15, generated by Stage 1
│   ├── language_vectors.npy                # 1.17M × 20, generated by Stage 1
│   ├── runtime_normalized.npy              # 1.17M × 1, generated by Stage 1
│   ├── mood_scores.npy                     # 1.17M × 7, generated by Stage 2
│   ├── quality_scores.npy                  # 1.17M × 1, generated by Stage 3
│   ├── movie_id_index.json                 # movie_id ↔ row_index, generated by Stage 4
│   ├── keyword_mood_map.json               # ~70K keyword → mood predictions, generated by classifier
│   └── svd_models/                         # Fitted SVD transformers (.pkl), generated by Stage 1
│       ├── keyword_svd.pkl
│       ├── director_svd.pkl
│       └── actor_svd.pkl
│
├── notebooks/                              # TRACKED — Jupyter notebooks
│   └── ml_evaluation.ipynb                 # Detailed ML evaluation (academic, narrative)
│
├── docs/                                   # TRACKED — Project documentation
│   ├── CONTRIBUTION.md                     # Team contribution matrix
│   ├── REQUIREMENTS.md                     # Grading requirements checklist
│   ├── TMDB_API.md                         # TMDB API endpoint reference
│   ├── ML-PIPELINE.md                      # Offline pipeline + ML evaluation spec
│   ├── SCORING.md                          # Scoring formula + component details
│   ├── FILTER.md                           # 14 discovery filters
│   ├── MOOD.md                             # Keyword-to-mood classification
│   ├── tmdb-schema.mmd                     # ER diagram of TMDB database (Mermaid)
│   ├── concept/                            # Original project concept
│   │   ├── cs-project.md                   # Project concept (Markdown)
│   │   ├── cs-project.docx                 # Project concept (original Word)
│   │   ├── OPEN_ISSUES.md                  # Resolved conceptual gaps
│   │   └── prototype-movie-recommender.jpg # Wireframe prototype
│   └── references/                         # Course reference materials
│       ├── group-project.pdf               # Grading rubric (11 slides)
│       ├── group-project.mp4               # Project briefing recording
│       ├── 02-exercises.pdf                # Exercise reference
│       ├── 04-prep-streamlit.mp4           # Streamlit prep recording
│       └── writing-with-ai.md              # AI usage policy
│
├── .streamlit/                             # PARTIAL — Config tracked, secrets gitignored
│   ├── config.toml                         # Cinema Gold theme + fontFaces + server config
│   ├── secrets.toml                        # API keys (gitignored)
│   └── secrets.toml.example                # Template for secrets
│
├── CLAUDE.md                               # Claude Code project instructions
├── MIGRATION.md                            # Migration plan + implementation roadmap
├── README.md                               # Project overview
├── TODO.md                                 # Task tracking with deadlines
└── requirements.txt                        # Python dependencies
```

---

## Running the App

```bash
conda activate ./.conda
streamlit run app/streamlit_app.py
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
- Imports relative to `app/`: `from utils.tmdb import get_genres`
- Pages directory: `app_pages/` (not `pages/` — conflicts with old Streamlit API)
- State initialization: `st.session_state.setdefault()` in entry point
- UX pattern: Each tab has one responsibility. Poster grids on Rate and Watchlist, click → detail dialog overlay (`@st.dialog`)

### Page Descriptions (current state)

- **Discover:** Genre-only filter + card-based one-at-a-time browsing. 19 TMDB genre toggle buttons (AND logic), automatic pagination up to 10 pages, already-rated/dismissed/watchlisted movies filtered out. Toast feedback on watchlist add and dismiss.
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
- Fonts: Poppins (Google Fonts, OFL licensed) served via `enableStaticServing = true` from `app/static/`. 18 TTF files (weights 100-900, normal + italic) registered as `[[theme.fontFaces]]` in config.toml.

---

## Planned Features (authoritative source: MIGRATION.md)

**All planned features, architecture decisions, scoring formulas, ML pipeline details, and implementation roadmap are defined in [MIGRATION.md](MIGRATION.md).** That file is the single source of truth for all Soll-Zustand. Consult it before implementing any new feature.

Supporting docs (referenced by MIGRATION.md):
- [docs/ML-PIPELINE.md](docs/ML-PIPELINE.md) — offline pipeline stages, ML evaluation spec
- [docs/SCORING.md](docs/SCORING.md) — scoring formula, dynamic weights, component details
- [docs/FILTER.md](docs/FILTER.md) — 14 discovery filters, API parameter mapping, caching
- [docs/MOOD.md](docs/MOOD.md) — keyword-to-mood classification, labeling methodology

Key planned changes (see MIGRATION.md for full details):
- Discover: 14 filter controls + personalized ML scoring (Phase 2 + 4)
- Rate: "Based on your interests" personalized poster grid (Phase 4)
- Watchlist: mood reactions in "Mark as watched" dialog (Phase 4)
- Statistics: ML evaluation section + mood distribution chart (Phase 3 + 4)
- Offline pipeline: feature extraction, mood prediction, quality scores (Phase 1a)
- Keyword-to-mood classifier: supervised pipeline on 1,049 labeled keywords (Phase 1b)
- Online scoring: user profile + 9-signal cosine similarity (Phase 2)

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
| 5 | Machine learning | In progress — see [MIGRATION.md](MIGRATION.md) Phase 1-3 |
| 6 | Code documentation | In progress |
| 7 | Contribution matrix | Not started |
| 8 | 4-min video | Not started |

---

## Navigation

- **Parent:** /Users/home/Developer/projects/hsg/cs/CLAUDE.md
