# Movie Recommender

A Streamlit web app that recommends movies based on user preferences and ratings, with ML-based personalization.

**Course:** 4,125 Grundlagen und Methoden der Informatik, FS26
**University:** University of St. Gallen (HSG)
**Deadline:** May 14, 2026

---

## Problem Statement

With thousands of movies available across streaming platforms, users waste time scrolling without finding something they'd enjoy. This app solves that by learning from the user's ratings and mood reactions to deliver personalized recommendations — replacing aimless browsing with targeted discovery.

![Discover Page](docs/images/landing_page.png)

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

| Component   | Technology                                                                                                                                 |
|-------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| Frontend    | [Streamlit](https://streamlit.io)                                                                                                          |
| Theme       | "Cinema Gold" — dark base, gold/copper accent, [Poppins](https://fonts.google.com/specimen/Poppins) font (18 weight/style variants)        |
| Language    | Python 3.11                                                                                                                                |
| Data source | [TMDB API v3](https://developer.themoviedb.org/docs/getting-started) — 9 endpoints, cached with TTLs (5m-24h)                              |
| User data   | SQLite (WAL mode) — 8 tables: ratings, moods, watchlist, dismissed, subscriptions, preferences, profile cache, movie details (JSON columns)|
| ML offline  | scikit-learn (TF-IDF, TruncatedSVD, 7 classifiers), transformers (distilroberta), sentence-transformers (EmbeddingGemma-300M)              |
| ML online   | Precomputed `.npy` arrays (~3 GB, 1.17M movies), numpy-vectorized 11-signal cosine similarity scoring (~8ms / 300 candidates)              |

---

## Features

| Page       | Key Features                                                                                                                  |
|------------|-------------------------------------------------------------------------------------------------------------------------------|
| Discover   | 8 sidebar filters, 7 mood pills, 4 sort options (incl. ML-personalized), poster grid, detail dialogs with trailer + actions   |
| Rate       | TMDB title search, personalized browse grid, 0-100 rating slider with color-coded track + 7 mood reaction pills               |
| Watchlist  | Poster grid of saved movies, streaming provider logos, trailer, "Watch Now" link, rate-on-watch flow                          |
| Statistics | 4 KPIs, genre/mood bar charts (Altair), user-vs-TMDB scatter plot with regression, top 5 directors + actors, ratings table    |
| Settings   | Streaming country, provider subscriptions (logo grid with toggle), preferred language, factory reset                          |

---

## ML Pipeline

The offline pipeline processes a 7.7 GB TMDB database (1.17M movies) into ~3 GB of precomputed feature arrays:

| Stage                  | Script                 | Output                                                                     | Runtime   |
|------------------------|------------------------|----------------------------------------------------------------------------|-----------|
| 1. Feature extraction  | `src/ml/features.py`   | 7 `.npy` arrays (SVD 200-dim, genre, decade, language, runtime) + 3 `.pkl` | ~3 min    |
| 1b. Keyword classifier | `src/ml/classifier.py` | `keyword_mood_map.json` (68K keywords → 7 moods)                           | ~3 min    |
| 2. Mood prediction     | `src/ml/moods.py`      | `mood_scores.npy` (1.17M × 7 moods, 4 combined signals)                    | ~4h       |
| 3. Quality scores      | `src/ml/quality.py`    | `quality_scores.npy` (Bayesian average, normalized [0,1])                  | <1s       |
| 4. Index + verify      | `src/ml/index.py`      | `movie_id_index.json` + consistency check                                  | <1s       |

At runtime, candidates from the TMDB API are re-ranked using **10 weighted similarity signals** (keyword, mood, genre, director, actor, decade, language, runtime, quality, contra penalty). Weights shift dynamically from quality-heavy (cold start) to personalization-heavy (50+ ratings). See `src/scoring/SCORING.md`.

### ML Evaluation

Full course-compliant evaluation in `evaluation.ipynb`: 7 classifiers (KNN, SVC, GaussianNB, LogisticRegression, MLPClassifier, 2× Dummy), scaled vs unscaled comparison, 80/10/10 split, confusion matrix, 10-fold cross-validation, KNN k-tuning. Best model: MLPClassifier (89% val accuracy, 0.76 macro F1).

**Beyond course:** TF-IDF + TruncatedSVD on 1.17M movies, pre-trained emotion transformer, EmbeddingGemma-300M embeddings, Bayesian quality scoring, 11-signal content-based scoring with dynamic weights.

---

## Directory Structure

```
movie-recommender/
├── app.py				# entry point
├── evaluation.ipynb			# ML evaluation notebook
├── contribution.md			# team contribution matrix
├── contribution.png			# visual contribution matrix (to be generated)
├── requirements.txt			# pip dependencies
├── README.md				# this file
│
├── video/				# 4-minute demo video (Req 8)
│
├── src/
│   ├── constants.py			# app-wide constants (moods, colors, thresholds)
│   ├── db.py				# SQLite persistence layer
│   ├── tmdb.py				# TMDB API v3 client
│   ├── helpers.py			# data helpers (no Streamlit)
│   ├── components.py			# reusable Streamlit UI renderers
│   ├── DATA.md				# documentation for db.py + tmdb.py
│   │
│   ├── views/
│   │   ├── discover.py			# discover page (filters, mood pills, poster grid)
│   │   ├── rate.py			# rate page (search, browse, rating slider)
│   │   ├── watchlist.py		# watchlist page (saved movies, streaming info)
│   │   ├── statistics.py		# statistics page (charts, rankings, ratings table)
│   │   ├── settings.py			# settings page (country, subscriptions, language)
│   │   └── VIEWS.md			# view architecture documentation
│   │
│   ├── scoring/
│   │   ├── loader.py			# lazy singleton: load .npy arrays
│   │   ├── profile.py			# user profile computation
│   │   ├── cache.py			# profile SQLite cache
│   │   ├── rank.py			# 11-signal candidate scoring
│   │   ├── mood.py			# mood threshold filter
│   │   └── SCORING.md			# scoring architecture documentation
│   │
│   └── ml/
│       ├── run.py			# pipeline runner (single entry point)
│       ├── features.py			# stage 1: TF-IDF, SVD, onehot vectors
│       ├── classifier.py		# stage 1b: keyword-to-mood classifier
│       ├── moods.py			# stage 2: 4-signal mood prediction
│       ├── quality.py			# stage 3: Bayesian quality scores
│       ├── index.py			# stage 4a: movie ID index
│       ├── verify.py			# stage 4b: pipeline output verification
│       └── PIPELINE.md			# ML pipeline documentation
│
├── data/
│   ├── source/
│   │   ├── tmdb.sqlite			# 7.7 GB offline database (gitignored)
│   │   ├── labeled_keywords.tsv	# training data (5K labeled keywords)
│   │   ├── genre_mood_map.json		# 19 genre-to-mood rules
│   │   └── SOURCE.md			# pipeline source data documentation
│   ├── models/
│   │   ├── *_svd_vectors.npy		# SVD feature arrays (3× 939 MB, gitignored)
│   │   ├── *.pkl			# fitted SVD models (gitignored)
│   │   ├── genre_vectors.npy		# genre multi-hot (89 MB)
│   │   ├── decade_vectors.npy		# decade one-hot (70 MB)
│   │   ├── language_vectors.npy	# language one-hot (94 MB)
│   │   ├── runtime_normalized.npy	# normalized runtime (4.7 MB)
│   │   ├── popularity_normalized.npy	# log-normalized popularity (4.7 MB)
│   │   ├── mood_scores.npy		# 1.17M × 7 mood probabilities (33 MB)
│   │   ├── quality_scores.npy		# Bayesian averages (4.7 MB)
│   │   ├── movie_id_index.json		# ID ↔ row mapping (19 MB)
│   │   ├── keyword_mood_map.json	# 68K keyword-to-mood entries (3.1 MB)
│   │   └── MODELS.md			# pipeline output documentation
│   └── user.sqlite			# user data (created at runtime, gitignored)
│
├── docs/
│   ├── concept.md			# original project concept
│   ├── wireframes.md			# UI flow diagram + comparison
│   ├── requirements.md			# course requirements mapping
│   ├── classifier_results.csv		# classifier comparison results
│   ├── TODO.md				# remaining tasks before submission
│   └── images/
│       ├── landing_page.png		# app screenshot
│       ├── confusion_matrix.png	# classifier evaluation
│       ├── prototype-original.jpg	# original UI mockup
│       └── wireframe-pages.png		# current UI wireframe (needs update)
│
├── static/
│   ├── Poppins-*.ttf			# 6 font weight variants
│   └── OFL.txt				# Open Font License
│
└── .streamlit/
    ├── config.toml			# theme configuration
    ├── secrets.toml			# API keys (gitignored)
    └── secrets.toml.example		# template for API key setup
```

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
streamlit run app.py
```

---

## Deployment

Public URL: **https://hsg.adlerscope.com** (Cloudflare Tunnel)
