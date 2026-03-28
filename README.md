# Movie Recommender

A Streamlit web app that recommends movies based on user preferences and ratings, with ML-based personalization.

**Course:** 4,125 Grundlagen und Methoden der Informatik, FS26
**University:** University of St. Gallen (HSG)
**Deadline:** May 14, 2026

---

## Problem Statement

With thousands of movies available across streaming platforms, users waste time scrolling without finding something they'd enjoy. This app solves that by learning from the user's ratings and mood reactions to deliver personalized recommendations — replacing aimless browsing with targeted discovery.

---

## Team

| Handle            | Name       |
|-------------------|------------|
| @AdlerView        | Constantin |
| @antoineleger-lab | Antoine    |
| @dede3718         | Dany       |
| @elgrandekomir    | Mirko      |

---

## Tech Stack

| Component   | Technology |
|-------------|------------|
| Frontend    | [Streamlit](https://streamlit.io) (mandatory) |
| Theme       | "Cinema Gold" — dark base, gold/copper accent, [Poppins](https://fonts.google.com/specimen/Poppins) font (18 weight/style variants via static serving) |
| Language    | Python 3.11 |
| Data source | [TMDB API v3](https://developer.themoviedb.org/docs/getting-started) — 9 endpoints, cached with TTLs (5m-24h) |
| User data   | SQLite (WAL mode) — 8 tables: ratings, moods, watchlist, dismissed, subscriptions, preferences, profile cache, movie details (JSON columns) |
| ML offline  | scikit-learn (TF-IDF, TruncatedSVD, 7 classifiers), transformers (distilroberta emotion classifier), sentence-transformers (EmbeddingGemma-300M) |
| ML online   | Precomputed `.npy` arrays (~3 GB, 1.17M movies), numpy-vectorized 11-signal cosine similarity scoring (~8ms / 300 candidates) |

---

## Features

### Discover — Personalized Movie Discovery

- **8 sidebar filters:** genre (multi-select pills), year range, runtime range, TMDB rating range, minimum vote count, age certification, keyword search (autocomplete with removable chips)
- **Mood pills:** 7 Ekman emotion categories (Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry) as multi-select toggle pills, filtering against precomputed mood scores
- **4 sort options:** Personalized (ML scoring), Popularity, Rating, Release date
- **Poster grid:** 5-column clickable poster grid with CSS overlay buttons, pagination via "Load more"
- **Detail dialog:** two-column layout (metadata + cast photos), YouTube trailer embed, genre/rating badges, streaming provider logos, "Add to watchlist" / "Not interested" actions
- **Fallback:** "You might also like" popular movies when filters return no results
- **Preferences from Settings:** streaming country, subscriptions, and language applied automatically from SQLite

### Rate — Search and Rate Movies

- **TMDB text search:** find movies by title with instant results
- **Personalized browse grid:** "Based on your interests" (ML-scored via `discover/movie` endpoint) or "Discover movies" (popularity order on cold start)
- **Rating dialog:** 0-100 slider (steps of 10) with color-coded track (gray/red/orange/green), dot tick marks, dynamic sentiment label (Awful → Masterpiece)
- **Mood reactions:** 7 optional mood pills per rating, saved alongside the numeric score
- **Re-rating:** rated movies excluded from browse grid but appear in search results for re-rating
- **Exclusion policy:** rated + dismissed + watchlisted movies filtered from browse grid

### Watchlist — Saved Movies with Streaming Info

- **Poster grid:** Netflix-style clickable posters with deduplication guard
- **Detail dialog:** streaming provider logos for user's country, runtime, YouTube trailer, "Watch Now" link (TMDB)
- **Actions:** "Remove from watchlist" or "Mark as watched" (opens rating slider + mood pills, then moves to rated)

### Statistics — Personal Taste Dashboard

- **KPIs:** movies rated, total watch hours, average rating, watchlisted count
- **Genre preferences:** horizontal bar chart colored by average user rating (Altair)
- **Mood profile:** horizontal bar chart with emoji labels showing mood reaction distribution
- **You vs TMDB:** scatter plot with diagonal reference line, color-coded deviation, trend regression
- **Favorite directors + actors:** top 5 each with profile photos, movie count, average rating
- **Rated movies table:** sortable with title, TMDB score (1 decimal), user rating (progress bar)
- **Zero API calls:** all data from local SQLite with `json_each()` aggregations

### Settings — Preferences Management

- **Streaming country:** dropdown (245 countries), auto-saved on change, determines provider availability on Discover
- **Subscriptions:** clickable provider logo grid (6 columns, top 30 providers per country) with green checkmark overlay on selected, auto-saved on toggle
- **Preferred language:** dropdown, auto-saved on change, applied as default original language filter on Discover
- **Reset to factory settings:** one-click reset of all three preferences

### ML Pipeline — Offline Feature Extraction

The offline pipeline processes a 7.7 GB TMDB database (1.17M movies, 30 tables) into ~3 GB of precomputed feature arrays:

| Stage | Script | Output | Runtime |
|-------|--------|--------|---------|
| 1. Feature extraction | `ml/extraction/extract_features.py` | 7 `.npy` arrays (keyword/director/actor SVD 200-dim, genre 19-dim, decade 15-dim, language 20-dim, runtime) + 3 `.pkl` SVD models | ~3 min |
| 1b. Keyword classifier | `ml/classification/keyword_mood_classifier.py` | `keyword_mood_map.json` (68,462 keywords → 7 moods) + confusion matrix + results CSV | ~3 min |
| 2. Mood prediction | `ml/classification/predict_moods.py` | `mood_scores.npy` (1.17M × 7), 4 signals: genre, keyword, overview emotion, review emotion | ~4h 18min |
| 3. Quality scores | `ml/extraction/quality_scores.py` | `quality_scores.npy` (Bayesian average, normalized [0,1]) | <1s |
| 4. Build index | `ml/extraction/build_index.py` | `movie_id_index.json` (bidirectional ID↔row mapping) + verification | <1s |

### ML Pipeline — Online Scoring (10 Signals)

At runtime, candidate movies from the TMDB API are re-ranked using 10 weighted similarity signals:

| Signal | Weight (50+ ratings) | Method |
|--------|---------------------|--------|
| Keyword similarity | 0.20 | Cosine similarity of keyword SVD vectors |
| Mood match | 0.20 | Explicit mood selection or implicit mood profile |
| Director similarity | 0.15 | Cosine similarity of director SVD vectors |
| Actor similarity | 0.10 | Cosine similarity of actor SVD vectors |
| Quality score | 0.10 | Precomputed Bayesian average |
| Contra penalty | 0.10 | Negative cosine sim against disliked themes |
| Genre similarity | 0.05 | Cosine similarity of genre multi-hot vectors |
| Decade similarity | 0.05 | Cosine similarity of decade one-hot vectors |
| Language similarity | 0.03 | Cosine similarity of language one-hot vectors |
| Runtime similarity | 0.02 | 1 - |user_pref - candidate| |

Weights shift dynamically: cold start → quality-heavy (0.60), 50+ ratings → personalization-heavy (see `ml/scoring/SCORING.md`).

### ML Evaluation — Academic Compliance

Full course-compliant ML evaluation workflow (see `ml/evaluation/ml_evaluation.ipynb`):

- **7 classifiers compared:** KNN, SVC, GaussianNB, LogisticRegression, MLPClassifier, 2× DummyClassifier (most_frequent, stratified)
- **Scaled vs unscaled comparison:** RobustScaler, fit on train only
- **80/10/10 split:** train/val/test, stratified, fixed seed
- **Best model:** MLPClassifier (89% val accuracy, 0.76 macro F1)
- **Confusion matrix + classification report** on held-out test set
- **10-fold cross-validation** with mean ± std accuracy
- **KNN hyperparameter tuning:** k=1..20, train vs validation accuracy plot
- **Beyond course:** TF-IDF + TruncatedSVD (1.17M movies), pre-trained emotion transformer, EmbeddingGemma-300M embeddings, Bayesian quality scoring, 11-signal content-based scoring with dynamic weights

---

## Directory Structure

```
movie-recommender/
├── streamlit_app.py           Entry point (config, DB init, navigation)
├── app/
│   ├── views/                 5 page modules (discover, rate, watchlist, statistics, settings)
│   └── utils/                 DB persistence (db.py) + TMDB API client (tmdb.py)
├── ml/
│   ├── extraction/            Offline: feature vectors from tmdb.sqlite → .npy arrays
│   ├── classification/        Offline: keyword-to-mood classifier + mood score prediction
│   ├── scoring/               Online: user profile, 11-signal scoring, mood filter
│   └── evaluation/            ML evaluation functions + Jupyter notebook
├── data/
│   ├── input/                 Pipeline sources (tmdb.sqlite, labeled keywords, genre-mood map)
│   └── output/                Pipeline outputs (.npy arrays, .json mappings, .pkl models)
├── docs/                      Project documentation + archive
├── static/                    Poppins font files (18 TTFs, OFL licensed)
└── .streamlit/                Theme config (tracked) + secrets (gitignored)
```

---

## Grading Criteria

8 requirements, each scored 0-3 points. Project = 20% of final grade. Source: [group-project.pdf](docs/group-project.pdf).

| Points | Description |
|--------|-------------|
| 0 | Requirement not met / feature does not exist |
| 1 | Basic implementation, formally present but not very relevant to the problem |
| 2 | Good implementation |
| 3 | Outstanding implementation, far beyond the level of this course |

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Problem clearly stated | ✅ defined (README + original-concept.md) |
| 2 | Data via API/database | ✅ implemented (TMDB API v3, 9 endpoints + SQLite, 8 tables + 1.17M movie DB) |
| 3 | Data visualization | ✅ implemented (4 KPIs, 4 Altair charts, top 5 rankings, sortable table) |
| 4 | User interaction | ✅ implemented (8 filters, mood pills, ratings, watchlist, settings, 5 pages) |
| 5 | Machine learning | ✅ implemented (TF-IDF/SVD pipeline, 11-signal scoring, 7 classifiers, evaluation) |
| 6 | Code documentation | ✅ implemented (Google-style docstrings, inline comments, 16 .md files) |
| 7 | Contribution matrix | ⚠️ structure ready, needs team input |
| 8 | 4-min video + demo | ❌ not started |

Detailed mapping: [docs/requirements-mapping.md](docs/requirements-mapping.md)

| Points | Grade % | Points | Grade % |
|--------|---------|--------|---------|
| ≤8 | ≤50% | 13 | 81.25% |
| 9 | 56.25% | 14 | 87.5% |
| 10 | 62.5% | 15 | 93.75% |
| 11 | 68.75% | ≥16 | 100% |
| 12 | 75% | | |

---

## Project Docs

| Document | Description |
|----------|-------------|
| [CONTRIBUTION.md](docs/CONTRIBUTION.md) | Team contribution matrix (Req 7) |
| [requirements-mapping.md](docs/requirements-mapping.md) | Course requirements → code mapping with score estimates |
| [wireframe-current.md](docs/wireframe-current.md) | Current UI flow (Mermaid diagram) |
| [wireframe-comparison.md](docs/wireframe-comparison.md) | Original concept vs final implementation |
| [original-concept.md](docs/original-concept.md) | Original project concept |

---

## GenAI Citation Policy

Using AI (ChatGPT, Claude, etc.) to **learn concepts** does not require citation. Having AI **write larger code blocks** requires citing the source in a comment. AI-generated code without citation is plagiarism. See [HSG GenAI rules](https://universitaetstgallen.sharepoint.com/sites/PruefungenDE/SitePages/Arbeiten-mit-KI.aspx).

---

## Setup

```bash
# Create environment
conda create --prefix ./.conda python=3.11
conda activate ./.conda

# Install dependencies
pip install -r requirements.txt

# Configure API key
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with the shared TMDB API key

# Run the app
streamlit run streamlit_app.py
```

---

## Deployment

Public URL: **https://hsg.adlerscope.com** (Cloudflare Tunnel)

```bash
# Start Streamlit
conda activate ./.conda
streamlit run streamlit_app.py

# Start tunnel (separate terminal)
cloudflared tunnel --config ~/Developer/.config/cloudflared/config.yml run movie-recommender
```
