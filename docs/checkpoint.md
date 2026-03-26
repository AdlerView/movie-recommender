# Session Checkpoint — 2026-03-26

## Current Status

Major restructuring session. Built the entire offline ML pipeline, redesigned the Discover page, added ML evaluation to Statistics, and iteratively refined the directory structure. A final large restructuring is planned but NOT yet executed.

## What Was Accomplished (high confidence, all committed and pushed)

### ML Pipeline (Phase 1a + 1b) — COMPLETE
- `ml/classification/keyword_mood_classifier.py`: trained MLPClassifier on 1,049 labeled keywords (val F1=0.76, test acc=78%), inferred 68,462 keyword moods. Output: `data/output/keyword_mood_map.json`
- `ml/extraction/01_extract_features.py`: 7 feature arrays from tmdb.sqlite (keyword/director/actor SVD 200-dim, genre/decade/language onehot, runtime). Runtime: 2m39s. Output: 7 `.npy` + 3 `.pkl` in `data/output/`
- `ml/classification/02_predict_moods.py`: 4 signals (genre, keyword, overview emotion via distilroberta, review emotion). Runtime: 4h18m. Output: `data/output/mood_scores.npy` (31.4 MB, 94.6% coverage)
- `ml/extraction/03_quality_scores.py`: Bayesian average. Output: `data/output/quality_scores.npy`
- `ml/extraction/04_build_index.py`: generates `data/output/movie_id_index.json`, verifies all 14 outputs
- `data/input/genre_mood_map.json`: 19 hand-crafted genre-to-mood rules

### Discover Page Redesign (Task 4.1) — COMPLETE
- Sidebar with 12 filters (genre pills, year slider, runtime/rating/min-votes sliders, keyword autocomplete + chips, expander with language/certification/streaming)
- Main page: mood pills (toggle-deselect), sort selectbox, poster grid (5 cols), detail dialog, load more, empty-state fallback with "You might also like"
- Live filtering (no Discover button)
- New TMDB API functions in `app/utils/tmdb.py`: discover_movies_filtered, get_languages, get_certifications, get_countries, get_watch_providers_list, search_keywords

### ML Evaluation (Tasks 3.1 + 3.2) — COMPLETE
- `ml/evaluation/ml_eval.py`: 4 generic functions (evaluate_classifiers, best_model_report, run_cross_validation, knn_hyperparameter_plot)
- Statistics page section: classifier comparison table (14 rows, scaled+unscaled), best model KPIs, confusion matrix PNG, button for live cross-validation (81.6% +/- 3.8%) and KNN k=1..20 plot

### Directory Restructuring (multiple iterations)
- Original: `data/` (mixed) + `model/` (gitignored)
- Then: `data/labeled/` + `data/evaluation/` + `store/` (gitignored)
- Then: `store/input/` + `store/output/`
- Then: `data/input/` + `data/output/` (renamed store→data)
- Then: merged `evaluation/` into `data/output/`
- Current state: `data/input/`, `data/output/`, `data/user.sqlite`
- Database renames: `tmdb.db` → `tmdb.sqlite`, `movies.db` → `user.sqlite`
- Removed: `data/labeled/tmdb-keyword-frequencies.tsv` (redundant), `store/exports/` (469 MB, unused)

## What Is NOT Yet Done

### CRITICAL: Final Directory Restructuring (planned, NOT executed)
A comprehensive prompt for a new session was written (in the conversation, not saved to a file). The target structure is documented in CLAUDE.md "Directory Structure" section (already updated). The changes are:

1. `streamlit_app.py` → `streamlit_app.py` (root)
2. `app/views/` → `app/views/`
3. `ml/` → split into `ml/extraction/`, `ml/classification/`
4. `ml/evaluation/ml_eval.py` → `ml/evaluation/ml_eval.py`
5. `docs/ML-PIPELINE.md` → `ml/extraction/ML-PIPELINE.md`
6. `docs/MOOD.md` → `ml/classification/MOOD.md`
7. `docs/SCORING.md` → `ml/scoring/SCORING.md`
8. `docs/FILTER.md` → `ml/scoring/FILTER.md`
9. `MIGRATION.md` → `docs/MIGRATION.md`
10. `TODO.md` → `docs/TODO.md`
11. Create 5 `__init__.py` files for ml/ packages
12. Update ~100 import paths (from utils.X → from app.utils.X)
13. Update ~50 doc references

**The CLAUDE.md already has the NEW target structure documented, but the filesystem still has the OLD structure.** This is an inconsistency that must be resolved — either execute the restructuring or revert CLAUDE.md.

### Phase 2: Online Scoring (PENDING, unblocked)
- `ml/scoring/user_profile.py` — compute user profile vectors from ratings + .npy arrays
- `ml/scoring/scoring.py` — 9-signal cosine similarity scoring with dynamic weights
- `ml/scoring/filters.py` — TMDB API parameter builder + local mood filter
- These files don't exist yet. They are the critical path to a functioning recommendation system.

### Phase 3.3: ML Evaluation Notebook (PENDING)
- `ml/evaluation/ml_evaluation.ipynb` — academic narrative for course requirement

### Phase 4.2 + 4.3 (PENDING, blocked by Phase 2)
- 4.2: Discover personalized sort option
- 4.3: Rate "Based on your interests" poster grid

### Phase 5: Polish + Deliverables (PENDING)
- Statistics dashboard polish
- Discover visual polish
- Code documentation pass (Req 6)
- Contribution matrix (Req 7)
- 4-minute video (Req 8)
- Canvas upload by 2026-05-14

## Key Decisions Made

- SVD components: 200 (pragmatic default, documented in script docstring)
- Emotion classifier: j-hartmann/emotion-english-distilroberta-base, 7 classes (including neutral→interested mapping), runs fully offline with HF_HUB_OFFLINE=1
- Keyword classifier: 80/10/10 split (random_state=13), scaled+unscaled comparison, MLPClassifier best
- Scoring formula: 9 signals with dynamic weights by rating count (0, 1-9, 10-49, 50+)
- Contra threshold: ratings below 40/100
- Genre has no minimum selection requirement
- Live filtering on Discover (no explicit Discover button)
- Sidebar only on Discover page
- Sort dropdown stays as st.selectbox (typing to filter is Streamlit limitation, not fixable)
- Streamlit `pages/` directory name avoided (auto-detection conflict)

## File Locations (CURRENT state, not target)

```
streamlit_app.py          ← entry point (should move to root)
app/views/*.py            ← views (should rename to app/views/)
app/utils/db.py               ← DB_PATH = data/user.sqlite
app/utils/tmdb.py             ← TMDB API client
ml/evaluation/ml_eval.py          ← should move to ml/evaluation/
app/utils/__init__.py
app/static/                   ← Poppins fonts (must stay relative to entry point)
ml/*.py                 ← should split into ml/extraction/ + ml/classification/
data/input/tmdb.sqlite        ← GITIGNORED (7.7 GB)
data/input/genre_mood_map.json
data/input/tmdb-keyword-frequencies_labeled_top5000.tsv
data/output/*.npy, *.pkl, *.json, *.csv, *.png
data/user.sqlite              ← GITIGNORED
docs/*.md + concept/ + references/
CLAUDE.md                     ← HAS NEW TARGET STRUCTURE (inconsistent with filesystem!)
MIGRATION.md                  ← should move to docs/
TODO.md                       ← should move to docs/
```

## Import Path Changes Required (for restructuring)

All view files currently use:
```python
from app.utils.db import ...      →  from app.utils.db import ...
from app.utils.tmdb import ...    →  from app.utils.tmdb import ...
```

statistics.py currently uses:
```python
from ml.evaluation.ml_eval import ... →  from ml.evaluation.ml_eval import ...
```

streamlit_app.py currently uses:
```python
from app.utils.db import ...      →  from app.utils.db import ...
st.Page("app/views/discover.py") → st.Page("app/views/discover.py")
```

## Risks and Uncertainties

- **app/static/ path dependency** (high confidence): Streamlit's enableStaticServing requires static/ relative to the entry point. If streamlit_app.py moves to root, static/ must be at root level OR stay under app/ and the config adjusted. Currently documented to stay at app/static/. VERIFY this works after the move.

- **st.Page() path resolution** (medium confidence): st.Page("app/views/discover.py") should work relative to the entry point's directory. But test this.

- **ml/scoring/ runtime imports** (high confidence): These will be imported by the Streamlit app at runtime. They need __init__.py and the import path from ml.scoring.scoring will work because streamlit_app.py is at root.

- **Pipeline script CWD dependency** (high confidence): argparse defaults like Path("data/input/tmdb.sqlite") are relative to CWD, not script location. Works as long as scripts are run from project root regardless of where they're stored.

- **Git rename detection** (medium confidence): Moving files with git should show as renames if the content doesn't change much. Stage all moves together before committing.

## Prompt for Next Session

A comprehensive restructuring prompt (~1500 words) was composed in the conversation. It covers all 9 change categories in detail. Copy it from the conversation or regenerate from this checkpoint + CLAUDE.md target structure.

## Git State

Latest commit: c7ced81 (or later — several commits were made after)
Branch: main
Remote: github.com:AdlerView/movie-recommender.git
All changes committed and pushed. No uncommitted work except the CLAUDE.md target structure update.

Wait — actually CLAUDE.md was updated with the new target structure. Check if that was committed. If not, it needs to be committed before the restructuring session, otherwise the new session won't see the target.

## Deadline

2026-05-14 (Canvas upload). ~7 weeks remaining. Phase 2 (Online Scoring) is the critical path to a functioning recommendation system.
