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
| Persistence | SQLite (WAL mode, schema v4, normalized detail + keyword tables) + `keywords.db` (read-only keyword index) |
| ML          | spaCy word vectors + scikit-learn KNN (mood classification pipeline, planned) |

---

## Features

### Discover

Two-phase flow matching the wireframe prototype. First, select genre tags (19 TMDB genres), mood tags (curated feeling/atmosphere keywords), and keyword tags (top 30 from keyword index) — or skip to browse trending movies. Genres use **AND logic** as a hard filter via the TMDB API. Moods and keywords use **relevance ranking**: films are scored by how many selected moods/keywords they match (via a pre-populated local keyword index of ~50k movies), sorted by match count descending with TMDB popularity as tiebreaker. When moods/keywords are active, up to 5 pages (~100 movies) are pre-fetched to build a meaningful ranking pool. Then browse filtered movies one at a time in a card-based flow with three labeled badge sections: Genre (gray), Mood (gold/primary), Keywords (gray). Already-rated, dismissed, and watchlisted movies are all filtered out. Each movie can be added to the watchlist or dismissed. Automatic pagination loads the next page when all current movies are exhausted (up to 10 pages). No rating on this page — rating happens on the Rate page after you've seen the movie.

### Rate

Pure action tab for rating movies. A TMDB text search field at the top finds any movie by title. Below, a Netflix-style poster grid shows trending movies — posters are clickable via CSS overlay. Already-rated movies are excluded from the grid (auto-fetches extra pages to always show exactly 20). Clicking a poster opens a detail dialog with poster, genre/mood/keyword badge sections, TMDB rating, runtime, overview, and a 0.00-10.00 color-coded rating slider. Linear flow: search/browse → click → rate → done.

### Watchlist

Netflix-style poster grid of saved movies. Clicking a poster opens a detail dialog with genre/mood/keyword badge sections, TMDB rating, runtime, overview, and flatrate streaming providers for Switzerland (brand-colored: Netflix red, Amazon blue, Disney+ green, etc.). Actions: "Remove from watchlist" or "Mark as watched" which opens a rating slider — saving the rating moves the movie from watchlist to rated.

### Statistics

Dashboard powered by normalized SQLite data (zero API calls). KPI metrics: total watch hours, average runtime, rated/watchlisted/dismissed counts, average rating. Six Altair charts: genre distribution (horizontal bars, sorted by frequency), language distribution, decade distribution, rating distribution histogram, rating history line chart, and user vs TMDB scatter plot (with diagonal reference line). Top 5 favorite directors and actors rankings. Sortable table of all rated movies with poster thumbnails, title, duration, TMDB rating, and user rating (default sorted by user rating descending). Movie details + keywords eagerly cached on every rating save and backfilled on startup. Currently a proof of concept — layout and polish pending.

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
| 5 | Machine learning | planned (mood classification: spaCy + sklearn KNN) |
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

## Movie Recommender Status (as of 2026-03-24)

Last commit: `d39fae4` — "Add keyword scoring, mood badges, and centered headers to Discover"

### What's Done
- Full Streamlit app: Discover, Rate, Watchlist, Statistics pages
- TMDB API integration with caching
- SQLite persistence (ratings, watchlist, dismissed)
- keywords.db extraction complete (~50k movies, read-only keyword index)
- Keyword scoring integrated into Discover (genre AND filter + keyword/mood relevance ranking)
- Three badge sections (Genre gray, Mood primary, Keywords gray) on all movie cards/dialogs
- Cinema Gold theme, centered headers, clickable poster grids, rating slider UX
- Statistics PoC (KPIs, 6 Altair charts, rankings, rated movies table)

### Current Task: Mood Super-Categories in UI + ML Pipeline

**Seed keywords: DONE.** 165 curated mood keywords in 10 categories, verified against `keywords.db`, stored in `data/seed_keywords.json`. Each entry has TMDB `id`, `name`, and `frequency`. `MOOD_KEYWORD_NAMES` frozenset in `db.py` is synced (165 names).

**10 Mood Categories (165 keywords total):**

| Category | Count | Top keywords |
|----------|-------|-------------|
| Happy / Feel-Good | 19 | inspirational, playful, whimsical, hopeful, cheerful |
| Romantic / Warm | 16 | friendship, love, coming of age, admiring, romantic |
| Funny / Comedic | 16 | dark comedy, amused, absurd, romcom, satire |
| Exciting / Thrilling | 12 | survival, escape, suspenseful, intense, excited |
| Dark / Brooding | 23 | revenge, jealousy, betrayal, aggressive, obsession |
| Sad / Heavy | 21 | death, loss of loved one, grief, mental illness, tragedy |
| Eerie / Atmospheric | 19 | surrealism, horror, nightmare, surreal, mysterious |
| Nostalgic / Seasonal | 10 | christmas, holiday, fairy tale, halloween, nostalgic |
| Contemplative | 19 | ambiguous, transformation, thoughtful, philosophical, cautionary |
| Provocative / Bold | 10 | audacious, shocking, defiant, provocative, complex |

**Next: ML Pipeline (two phases):**
- **Phase 1 (Labeling, NOT ML):** spaCy `en_core_web_md` word vectors + cosine similarity. Use the 165 seed keywords as labeled anchors → compute centroid vectors per category → assign remaining ~34k keywords to nearest mood (with threshold for "no mood"). Semi-automatic labeling.
- **Phase 2 (ML, for grading Req 5):** sklearn KNeighborsClassifier trained on Phase 1 labels. Train/test split, evaluation metrics. Uses spaCy vectors as feature input. This is the demonstrable ML step.

**Script location:** `mood-classify.py`
**Input:** `data/keywords.db` (all unique keywords) + `data/seed_keywords.json` (165 labeled seeds)
**Output:** JSON mapping or dict for `MOOD_CATEGORIES` in db.py

**Next steps for UI:**
- Discover mood pills: show 10 category names instead of individual keywords
- On selection: expand category to all member keyword IDs for scoring
- Badge display: show category name on movie cards instead of raw keyword names

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
