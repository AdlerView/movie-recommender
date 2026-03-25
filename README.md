# Movie Recommender

A Streamlit web app that recommends movies based on user preferences and ratings, with ML-based personalization.

**Course:** Grundlagen und Methoden der Informatik, FS26
**University:** University of St. Gallen (HSG)

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
| Theme       | "Cinema Gold" — dark base, gold/copper accent (`#D4A574`), [Poppins](https://fonts.google.com/specimen/Poppins) font |
| Language    | Python |
| Data        | [TMDB API v3](https://developer.themoviedb.org/docs/getting-started) |
| Persistence | SQLite (WAL mode, schema v5) for user data. `tmdb.db` (1.17M movies, 30 tables, 8.2 GB) offline only. Runtime: precomputed `.npy` arrays (~3 GB) + TMDB API |
| ML          | Personalized recommendations via scikit-learn (content-based scoring from user ratings + mood reactions, feature vectors from tmdb.db) |

---

## Features

### Discover

Personalized movie discovery with 14 filter controls and ML-based ranking. Filters: Genre (19 TMDB genres, required), Mood (7 categories: Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry), Certification (country-dependent, e.g. DE: 0/6/12/16/18), Release Year range, Language, Runtime range, User Score range, Minimum Votes, Keywords (autocomplete via TMDB API `search/keyword`), Streaming Country, Streaming Provider, Only My Subscriptions, and Sort order. Filters are passed to the TMDB API `/discover/movie` endpoint for candidate retrieval. Mood filtering and personalized scoring run locally against precomputed `.npy` feature arrays (~3 GB, derived offline from `tmdb.db`). When sort is set to "Personalized Score" (default), results are ranked by an ML scoring model that combines keyword similarity, mood match, director/actor/decade/language/runtime similarity, quality score (Bayesian average), and contra-penalty — all derived from the user's rating history. Results displayed as card-based flow or poster grid with Genre/Keyword badges, predicted mood, runtime, streaming providers, and personalized score. Already-rated, dismissed, and watchlisted movies are filtered out. Cold-start: with 0 ratings, ranking falls back to quality + mood match; personalization strengthens with more ratings.

### Rate

Pure action tab for rating movies you've already seen. TMDB text search + Netflix-style clickable poster grid (trending). Clicking a poster opens a detail dialog with poster, keyword badges, TMDB rating, runtime, overview, a 0-100 color-coded rating slider (steps of 10), and 7 optional mood reaction buttons (Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry — based on TMDB's Vibes model / Ekman's basic emotions). Mood reactions are multi-select, saved alongside the numeric rating, and serve as training data for the personalized recommendation model. Save button is disabled until the slider is moved (prevents accidental 0-ratings). Linear flow: search/browse → click → rate (+ optional mood) → done.

### Watchlist

Netflix-style poster grid of saved movies. Clicking a poster opens a detail dialog with keyword badges, TMDB rating, runtime, overview, and flatrate streaming providers for the user's selected country (brand-colored: Netflix red, Amazon blue, Disney+ green, etc.). Actions: "Remove from watchlist" or "Mark as watched" which opens a rating slider with 7 mood reaction buttons — saving the rating moves the movie from watchlist to rated.

### Statistics

Dashboard powered by local user SQLite data (zero API calls). KPI metrics: total watch hours, average runtime, rated/watchlisted/dismissed counts, average rating. Altair charts: genre distribution, language distribution, decade distribution, rating distribution histogram, rating history line chart, user vs TMDB scatter plot, mood distribution (from user mood reactions). Top 5 favorite directors and actors rankings. Sortable table of all rated movies with poster thumbnails, title, duration, TMDB rating, and user rating. Currently a proof of concept — layout and polish pending.

### Persistence

All ratings, watchlist entries, and dismissals are persisted in a local SQLite database. Data loads on startup and saves on every action.

### TMDB Integration

Live data from TMDB API v3 with cached responses (genres 1h, trending 30m, discover 30m, search 5m, movie details 1h). Genre-based filtering via `/discover/movie`, trending via `/trending/movie/week`, text search via `/search/movie`. Movie details use `append_to_response=credits,videos,watch/providers` to fetch runtime, directors, cast, trailers, and streaming providers in a single API call. Error handling for API failures with user-facing messages.

---

## Deadlines

| Date       | Milestone | Status |
|------------|-----------|--------|
| 19/20.03   | Optional: project idea presentation I | |
| 26/27.03   | Optional: project idea presentation II | |
| 16/17.04   | Optional: MVP presentation I | |
| 23/24.04   | Optional: MVP presentation II | |
| **14.05**  | **Upload: code + video to Canvas (23:59)** | |
| **15.05**  | **Video presentation + Q&A (mandatory)** | |
| **21.05**  | **Top-3 presentation (mandatory)** | |

---

## Grading Criteria

8 requirements, each scored 0–3 points. Project = 20% of final grade. See [REQUIREMENTS.md](docs/REQUIREMENTS.md) for details.

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Problem clearly stated | defined |
| 2 | Data via API/database | implemented (TMDB + SQLite) |
| 3 | Data visualization | in progress (PoC: KPIs, 6 charts, rankings, table) |
| 4 | User interaction | implemented (discover/rate/dismiss/watchlist/search) |
| 5 | Machine learning | in progress (personalized recommendations: content-based scoring from user ratings + mood reactions, sklearn pipeline with classifier comparison) |
| 6 | Code documentation | in progress |
| 7 | Contribution matrix | not started |
| 8 | 4-min video + demo | not started |

---

## Project Docs

| Document | Description |
|----------|-------------|
| [TODO.md](TODO.md) | Actionable tasks with owners and deadlines |
| [REQUIREMENTS.md](docs/REQUIREMENTS.md) | Grading criteria with status tracking |
| [CONTRIBUTION.md](docs/CONTRIBUTION.md) | Team contribution matrix |
| [OPEN_ISSUES.md](docs/concept/OPEN_ISSUES.md) | Conceptual gaps and pending decisions |
| [cs-project.md](docs/concept/cs-project.md) | Original project concept |
| [Wireframe](docs/concept/prototype-movie-recommender.jpg) | UI prototype sketch |

Course reference material is in [docs/references/](docs/references/).

---

## GenAI Citation Policy

Using AI (ChatGPT, Claude, etc.) to **learn concepts** does not require citation. Having AI **write larger code blocks** requires citing the source in a comment. AI-generated code without citation is plagiarism. Full AI-generated programs are fine from a plagiarism perspective if cited, but hurt the contribution grade. See [HSG GenAI rules](https://universitaetstgallen.sharepoint.com/sites/PruefungenDE/SitePages/Arbeiten-mit-KI.aspx) ([local copy](docs/references/writing-with-ai.md)).

---

## Resources

- [Streamlit documentation](https://docs.streamlit.io/)
- [Streamlit cheat sheet](https://docs.streamlit.io/library/cheatsheet)
- [Streamlit tutorials (30 days)](https://30days-tmp.streamlit.app/)
- [Streamlit gallery](https://streamlit.io/gallery)
- [TMDB API reference](https://developer.themoviedb.org/reference/)

Optional extension (not graded, but improves the result): deploy publicly via [Streamlit Community Cloud](https://streamlit.io/cloud).

---

## Deployment

The app is publicly accessible at **https://hsg.adlerscope.com** via Cloudflare Tunnel.

| Component | Detail |
|-----------|--------|
| Tunnel name | `movie-recommender` |
| Protocol | QUIC |
| Service | `http://localhost:8501` (Streamlit) |
| Config | `~/Developer/.config/cloudflared/config.yml` |
| Credentials | `~/Developer/.local/share/cloudflared/movie-recommender.json` |

```bash
# Start Streamlit (Terminal 1)
conda activate ./.conda
streamlit run app/streamlit_app.py

# Start tunnel (Terminal 2)
cloudflared tunnel --config ~/Developer/.config/cloudflared/config.yml run movie-recommender
```

The tunnel requires both Streamlit and `cloudflared` to be running. TMDB API keys remain server-side (never sent to clients). Each browser tab gets an isolated Streamlit session.

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
# Edit .streamlit/secrets.toml and replace with the shared TMDB API key (see group chat)

# Run the app
streamlit run app/streamlit_app.py
```
