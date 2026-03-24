# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Created:** 2026-03-23
**Updated:** 2026-03-24

---

## Purpose

Movie recommender web app for HSG course 4,125 (Grundlagen und Methoden der Informatik, FS26). Group project worth 20% of final grade. Team of 4: Constantin, Antoine, Dany, Mirko. Deadline: May 14, 2026.

---

## Tech Stack

- **Framework:** Streamlit (>=1.53.0)
- **API:** TMDB API v3 (key in `.streamlit/secrets.toml`)
- **Database:** SQLite (WAL mode, schema versioned via `PRAGMA user_version`)
- **ML:** scikit-learn (content-based filtering, planned for weeks 10-11)
- **Python:** 3.11 (conda environment in `.conda/`)

---

## Directory Structure

```
movie-recommender/
├── app/
│   ├── streamlit_app.py          # Entry point (router)
│   ├── app_pages/                # Page modules
│   │   ├── discover.py
│   │   ├── watchlist.py
│   │   ├── rated.py
│   │   └── statistics.py
│   └── utils/                    # Business logic & helpers
│       ├── __init__.py
│       ├── db.py                 # SQLite persistence layer
│       └── tmdb.py
├── docs/                         # Project documentation
│   ├── CONTRIBUTION.md
│   ├── REQUIREMENTS.md
│   ├── TMDB_API.md
│   ├── concept/
│   └── references/
├── .streamlit/
│   ├── config.toml
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
- UX pattern: Two-phase discover flow (genre selection → movie browsing), card-based (one at a time)
- Pagination: Automatic page advancement when all movies on a page are exhausted (up to 10 pages)
- Rating: Decimal slider 0.00-10.00 in 0.01 steps (matching TMDB scale), color-coded track (gray/red/orange/green)
- Persistence: SQLite load-on-start, save-on-change; session state is runtime source of truth

---

## Grading Requirements

| # | Requirement | Status |
|---|------------|--------|
| 1 | Problem statement | Defined |
| 2 | Data via API | TMDB + SQLite integrated |
| 3 | Data visualization | Planned |
| 4 | User interaction | Implemented (rate/dismiss/watchlist) |
| 5 | Machine learning | Open (weeks 10-11) |
| 6 | Code documentation | In progress |
| 7 | Contribution matrix | Not started |
| 8 | 4-min video | Not started |

---

## Navigation

- **Parent:** /Users/home/Developer/projects/hsg/cs/CLAUDE.md
