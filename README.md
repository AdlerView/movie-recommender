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
| Theme       | "Cinema Gold" — dark base, gold/copper accent, [Poppins](https://fonts.google.com/specimen/Poppins) font |
| Language    | Python 3.11 |
| Data        | [TMDB API v3](https://developer.themoviedb.org/docs/getting-started) |
| Persistence | SQLite (WAL mode) for user data. Precomputed `.npy` feature arrays (~3 GB) for ML scoring |
| ML          | Personalized recommendations via scikit-learn (content-based scoring from user ratings + mood reactions) |

---

## Features

**Discover** — Personalized movie discovery with 14 sidebar filters (genre, year, runtime, rating, keywords, certification, streaming providers) and ML-based ranking. Mood pills filter by 7 emotion categories. Results displayed as a poster grid with detail dialogs. Cold-start falls back to popularity order.

**Rate** — Search or browse movies ("Based on your interests" when a profile exists). Click a poster to open a detail dialog with a 0-100 rating slider and 7 optional mood reaction buttons. Mood reactions serve as training data for personalization.

**Watchlist** — Poster grid of saved movies. Detail dialog shows streaming providers for the user's country. "Mark as watched" opens a rating dialog to move the movie from watchlist to rated.

**Statistics** — Dashboard with KPIs, 7 Altair charts (genre, language, decade, rating distribution, rating history, user vs TMDB scatter, mood distribution), top 5 directors/actors rankings, and a sortable rated movies table. All data from local SQLite, zero API calls.

**Settings** — Streaming country, subscription management, and preferred language. Preferences are persisted in SQLite and applied automatically on Discover.

---

## Directory Structure

```
movie-recommender/
├── app/          Streamlit views + utilities (DB, API client)
├── ml/           ML pipeline (extraction, classification, scoring, evaluation)
├── data/         Pipeline inputs (tmdb.sqlite) + outputs (.npy, .json, .pkl)
├── docs/         Project documentation + planning
├── static/       Poppins font files (18 TTFs)
└── .streamlit/   Theme config + secrets
```

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

8 requirements, each scored 0-3 points. Project = 20% of final grade. Source: [group-project.pdf](docs/archive/group-project.pdf).

| Points | Description |
|--------|-------------|
| 0 | Requirement not met / feature does not exist |
| 1 | Basic implementation, formally present but not very relevant to the problem |
| 2 | Good implementation |
| 3 | Outstanding implementation, far beyond the level of this course |

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Problem clearly stated | defined |
| 2 | Data via API/database | implemented (TMDB + SQLite) |
| 3 | Data visualization | implemented (KPIs, 7 Altair charts, rankings, rated movies table) |
| 4 | User interaction | implemented (discover/rate/dismiss/watchlist/search/settings) |
| 5 | Machine learning | implemented (offline pipeline + online scoring + ML evaluation) |
| 6 | Code documentation | in progress |
| 7 | Contribution matrix | not started |
| 8 | 4-min video + demo | not started |

| Points | Grade % | Points | Grade % |
|--------|---------|--------|---------|
| 0 | 0% | 9 | 56.25% |
| 1 | 6.25% | 10 | 62.5% |
| 2 | 12.5% | 11 | 68.75% |
| 3 | 18.75% | 12 | 75% |
| 4 | 25% | 13 | 81.25% |
| 5 | 31.25% | 14 | 87.5% |
| 6 | 37.5% | 15 | 93.75% |
| 7 | 43.75% | >=16 | 100% |
| 8 | 50% | | |

For task tracking see [docs/TODO.md](docs/TODO.md).

---

## Project Docs

| Document | Description |
|----------|-------------|
| [TODO.md](docs/TODO.md) | Actionable tasks with owners and deadlines |
| [CONTRIBUTION.md](docs/CONTRIBUTION.md) | Team contribution matrix |
| [cs-project.md](docs/archive/cs-project.md) | Original project concept |

Historical artifacts and course references are in [docs/archive/](docs/archive/).

---

## GenAI Citation Policy

Using AI (ChatGPT, Claude, etc.) to **learn concepts** does not require citation. Having AI **write larger code blocks** requires citing the source in a comment. AI-generated code without citation is plagiarism. Full AI-generated programs are fine from a plagiarism perspective if cited, but hurt the contribution grade. See [HSG GenAI rules](https://universitaetstgallen.sharepoint.com/sites/PruefungenDE/SitePages/Arbeiten-mit-KI.aspx) ([local copy](docs/archive/writing-with-ai.md)).

---

## Deployment

Public URL: **https://hsg.adlerscope.com** (Cloudflare Tunnel)

```bash
# Start Streamlit (Terminal 1)
conda activate ./.conda
streamlit run streamlit_app.py

# Start tunnel (Terminal 2)
cloudflared tunnel --config ~/Developer/.config/cloudflared/config.yml run movie-recommender
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
# Edit .streamlit/secrets.toml and replace with the shared TMDB API key (see group chat)

# Run the app
streamlit run streamlit_app.py
```

---

## Resources

- [Streamlit documentation](https://docs.streamlit.io/)
- [Streamlit cheat sheet](https://docs.streamlit.io/library/cheatsheet)
- [Streamlit tutorials (30 days)](https://30days-tmp.streamlit.app/)
- [Streamlit gallery](https://streamlit.io/gallery)
- [TMDB API reference](https://developer.themoviedb.org/reference/)
