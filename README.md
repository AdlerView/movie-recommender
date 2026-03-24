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
| Language    | Python |
| Data        | [TMDB API v3](https://developer.themoviedb.org/docs/getting-started) |
| Persistence | SQLite (WAL mode, schema-versioned) |
| ML          | TBD (content-based filtering planned) |

---

## Features

### Discover

Two-phase flow matching the wireframe prototype. First, select genre tags (19 TMDB genres as pills) and click Search — or skip to browse trending movies. Movies must match **all** selected genres (AND logic). Then browse filtered movies one at a time in a card-based flow (poster, genres, rating, overview). Rate movies on a 0.00-10.00 decimal slider (0.01 steps, matching TMDB scale). Each movie can be added to the watchlist or dismissed. Automatic pagination loads the next page when all current movies are exhausted (up to 200 movies).

### Watchlist

View all saved movies with posters, titles, TMDB ratings, and your rating (read-only display). To re-rate, use the Rated page.

### Rated

View and re-rate all movies you have rated, regardless of watchlist status. Each movie shows a slider to adjust your rating. Movies not in the watchlist have their metadata fetched from TMDB.

### Statistics

Dashboard with KPI metrics: number of watchlisted, rated, and dismissed movies, plus average rating.

### Persistence

All ratings, watchlist entries, and dismissals are persisted in a local SQLite database. Data loads on startup and saves on every action.

### TMDB Integration

Live data from TMDB API v3 with cached responses (genres 1h, trending 30m, discover 30m, movie details 1h). Genre-based filtering via `/discover/movie`, trending via `/trending/movie/week`. Error handling for API failures with user-facing messages.

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
| 3 | Data visualization | planned |
| 4 | User interaction | implemented (rate/dismiss/watchlist) |
| 5 | Machine learning | open |
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
