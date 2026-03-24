# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Created:** 2026-03-23
**Updated:** 2026-03-24



---

## Session Startup

At the start of every new session, read ALL of the following files before doing any work:

**Documentation (all `.md` files):**
- `CLAUDE.md`, `README.md`, `TODO.md`
- `docs/TMDB_API.md`, `docs/CONTRIBUTION.md`, `docs/REQUIREMENTS.md`
- `docs/concept/cs-project.md`, `docs/concept/OPEN_ISSUES.md`

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
- **Database:** SQLite (WAL mode, schema v4 via `PRAGMA user_version`) + `data/keywords.db` (read-only keyword index, ~63k movies)
- **ML:** Google EmbeddingGemma-300M via sentence-transformers (keyword embeddings, 256d Matryoshka) + scikit-learn KNN (mood classification). Pipeline: `scripts/mood_classify.py`, 170 curated seed keywords → 909 classified keywords in `keyword_moods` table in `keywords.db`
- **Python:** 3.11 (conda environment in `.conda/`)

---

## Directory Structure

```
movie-recommender/
├── app/
│   ├── streamlit_app.py          # Entry point (router)
│   ├── app_pages/                # Page modules
│   │   ├── discover.py           # Genre selection → movie browsing (no rating)
│   │   ├── rate.py               # Rate tab: search/browse → click poster → rate dialog
│   │   ├── watchlist.py          # Poster grid → detail dialog with streaming + actions
│   │   └── statistics.py         # KPIs, charts, rated movies table
│   ├── utils/                    # Business logic & helpers
│   │   ├── __init__.py
│   │   ├── db.py                 # SQLite persistence layer
│   │   └── tmdb.py
│   └── static/                   # Poppins font files (18 TTFs + OFL license)
├── scripts/
│   └── mood_classify.py           # Two-phase mood classification pipeline (EmbeddingGemma + KNN)
├── data/                            # Generated data (gitignored except .gitkeep + seed_keywords.json)
│   ├── keywords.db              # Pre-populated keyword index (~63k movies) + keyword_moods table (909 classified keywords)
│   ├── seed_keywords.json       # 170 curated mood keywords (10 categories, with TMDB IDs + frequencies)
│   └── .gitkeep
├── docs/                         # Project documentation
│   ├── CONTRIBUTION.md
│   ├── REQUIREMENTS.md
│   ├── TMDB_API.md
│   ├── concept/
│   └── references/
├── .streamlit/
│   ├── config.toml               # Cinema Gold theme + fontFaces + server config
│   ├── secrets.toml              # API keys (gitignored)
│   └── secrets.toml.example
├── CLAUDE.md
├── README.md
├── TODO.md
└── requirements.txt
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
- Discover: Two-phase flow (genre + mood + keyword selection → movie browsing), card-based one at a time, watchlist/dismiss only. Phase 1: three pill sections (Genre, Mood, Keywords) each with `st.subheader` + `st.pills(label_visibility="collapsed")`. Mood shows 10 ML-classified categories (Joyful, Romantic, Funny, Tense, Dark, Heavy, Eerie, Nostalgic, Contemplative, Provocative). Keywords shows top 30 popular + search popover for all ~34k keywords. Genres = hard AND filter (TMDB API). Moods + Keywords = hard relevance filtering via `data/keywords.db` (merged into one score, only movies with score > 0 shown, sorted by match count DESC, popularity as tiebreaker). With moods/keywords active, pre-fetches up to 5 pages (~100 movies) for ranking pool. Movie cards show keyword badges (Genre, Mood, Keywords), runtime, streaming providers (CH), and movie counter. Active filter badges displayed on browse phase. Filter state preserved on "Change filters" (pills restored from saved selections). Toast feedback on watchlist add and dismiss. Already-rated, dismissed, and watchlisted movies are all filtered out.
- Rate: Pure action tab. TMDB text search + Netflix-style clickable poster grid + trending. Click → dialog with details, keyword badges (Genre/Mood/Keywords sections), and rating slider. Already-rated movies excluded from trending grid but shown in search results (allows re-rating). "Search results" / "Trending movies" subtitles.
- Watchlist: Poster grid of saved movies. Click → dialog with TMDB details, keyword badges (Genre/Mood/Keywords sections), streaming providers (CH), "Remove from watchlist" and "Mark as watched" (with rating slider). Rating removes movie from watchlist.
- Statistics: KPIs, 6 Altair charts (genre, language, decade, rating distribution, rating history, user vs TMDB scatter), top directors + actors rankings, sortable rated movies table. All data from SQLite, zero API calls. PoC — layout polish pending.
- Pagination: Automatic page advancement on Discover (up to 10 pages), "Load more" button on Rate
- Rating: Decimal slider 0.00-10.00 in 0.01 steps (matching TMDB scale), color-coded track (gray/red/orange/green), dot tick marks at whole numbers, dynamic sentiment label (Awful/Poor/Decent/Great/Masterpiece). Save button disabled until slider is moved (prevents accidental 0-ratings). `on_change` callback sets `_*_touched_` flag in session state; flag cleaned up on save.
- TMDB rating display: Always 1 decimal (`:.1f`) across all pages for consistency.
- Dialog pattern: `on_click` sets `_*_selected_id` in session state, `@st.dialog` function called at end of script (dialogs cannot be triggered from callbacks directly)
- Movie details: Eagerly cached in normalized SQLite tables on every rating save + backfill on startup. Keywords fetched via separate endpoint (`get_movie_keywords`) with own backfill.
- Navigation: 4 pages — Discover, Rate, Watchlist (left-aligned), Statistics (right-aligned via CSS)
- Toolbar: `toolbarMode = "minimal"` hides Streamlit's Deploy button and menu
- Persistence: SQLite load-on-start, save-on-change; session state is runtime source of truth
- Headers: All page headers use `text_alignment="center"`. Section headers use `st.subheader` with `label_visibility="collapsed"` on the associated widget.
- Movie detail badges: Three labeled sections on all movie cards/dialogs (Discover, Rate, Watchlist). Genre = `:gray-badge`, Mood = `:primary-badge` (Cinema Gold), Keywords = `:gray-badge`. Section headers via `st.caption("**Genre**")` etc. Moods classified via `keyword_moods` table in `keywords.db` (909 keywords in 10 categories). `classify_movie_keywords()` in `db.py` splits keywords into mood categories (top 3 by relative score) and regular keywords. Sections only shown when data exists.
- Theme: All colors defined in `.streamlit/config.toml`, NOT in Python files. Dividers use `divider="gray"`, genre badges use `:gray-badge[...]`, mood badges use `:primary-badge[...]` (Cinema Gold accent). Only exception: functional slider colors (red/orange/green for rating feedback) and provider brand colors (Netflix=red etc.) remain in Python.
- Fonts: Poppins (Google Fonts, OFL licensed) served via `enableStaticServing = true` from `app/static/`. 18 TTF files (weights 100-900, normal + italic) registered as `[[theme.fontFaces]]` in config.toml.

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
| 3 | Data visualization | In progress (PoC: KPIs, 6 charts, rankings, table) |
| 4 | User interaction | Implemented (discover/rate/dismiss/watchlist/search) |
| 5 | Machine learning | Implemented (mood classification: EmbeddingGemma-300M + sklearn KNN, 909 keywords in 10 categories, integrated into UI) |
| 6 | Code documentation | In progress |
| 7 | Contribution matrix | Not started |
| 8 | 4-min video | Not started |

---

## Navigation

- **Parent:** /Users/home/Developer/projects/hsg/cs/CLAUDE.md
