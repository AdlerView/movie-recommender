# Requirements

> Grading criteria extracted from the course briefing.
> Each requirement is scored 0–3 points. The project accounts for 20% of the final grade.
> Source: [group-project.pdf](references/group-project.pdf)

---

## Scoring

| Points | Description |
|--------|-------------|
| 0      | Requirement not met / feature does not exist |
| 1      | Basic implementation, formally present but not very relevant to the problem |
| 2      | Good implementation |
| 3      | Outstanding implementation, far beyond the level of this course |

---

## Requirements

### 1. Problem Statement

> A problem that is solved by the application is clearly stated (e.g., business or consumer use case).

**Our approach:** With access to thousands of movies across all streaming platforms, it is easy to waste time searching for one to enjoy. Our app recommends movies based on user-selected genre tags and learns from ratings to improve suggestions over time.

**Status:** defined

---

### 2. Data via API / Database

> The application uses some data that is loaded via an API and/or provided via a database.

**Our approach:** TMDB API v3 — free, widely used, 158 API endpoints. Key endpoints: `/discover/movie` (genre-filtered results), `/trending/movie/{time_window}` (trending), `/movie/{id}` (details), `/genre/movie/list` (genre catalog), `/search/movie` (text search by title), `/movie/{id}/watch/providers` (streaming availability). Local SQLite database persists ratings (REAL 0.00-10.00), watchlist (JSON movie data), and dismissals across sessions. Schema versioned via `PRAGMA user_version`.

**Status:** implemented

---

### 3. Data Visualization

> The application visualizes some data that serves the use case.

**Our approach:** Statistics dashboard with KPI metrics (watch hours, avg runtime, rated/watchlisted/dismissed counts, avg rating), 5 Altair charts (genre distribution, decade distribution, language distribution, rating distribution histogram, user vs TMDB scatter plot, rating history line chart), top 5 directors + actors rankings, and sortable rated movies table with poster thumbnails. All data from normalized SQLite tables (zero API calls). Movie details + keywords eagerly cached on rating save + backfilled on startup.

**Status:** in progress (proof of concept — charts and data pipeline functional, layout and polish pending)

---

### 4. User Interaction

> The application allows for some user interaction, e.g., adding additional data, selecting certain data, running certain data analyses.

**Our approach:** Separated discover and rating flows across 4 pages. Discover: two-phase genre tag selection (19 TMDB genres as pills) → card-based movie browsing with "Add to watchlist" and "Not interested" buttons, automatic pagination (up to 10 pages). Rate: pure action tab — TMDB text search + Netflix-style clickable poster grid (CSS overlay), click opens `@st.dialog` with details + 0.00-10.00 color-coded rating slider with dot tick marks and sentiment labels. Already-rated movies excluded, auto-fetches extra pages. Watchlist: poster grid, click → dialog with streaming providers (CH), "Remove" or "Mark as watched" with rating slider. Statistics: KPI dashboard, genre chart, directors, sortable rated movies table. All actions persist to SQLite immediately.

**Status:** implemented

---

### 5. Machine Learning

> The application implements some machine learning.

**Our approach:** TBD. Content-based filtering is the most feasible option: build a user preference vector from rated films (weighted genres, directors, actors), compute similarity against candidates. ML lectures are in weeks 10–11 (07.05–15.05).

**Status:** open — see [OPEN_ISSUES.md #002](concept/OPEN_ISSUES.md)

---

### 6. Code Documentation

> The source code is well documented by comments in the source code.

**Our approach:** Google-style docstrings on all functions and modules, inline comments for non-obvious logic, API calls commented with endpoint and purpose, session state operations documented.

**Status:** in progress

---

### 7. Contribution Matrix

> The contributions of each team member are documented (e.g., contribution matrix).

**Our approach:** See [CONTRIBUTION.md](CONTRIBUTION.md).

**Status:** not started

---

### 8. Video

> The result is presented and demoed in a 4-minute video. The video is not allowed to use AI-generated voice overs.

**Our approach:** 4-minute screen recording with live narration by team members. Covers problem, approach, demo, contributions. **No AI-generated voice overs allowed** — all narration must be recorded by team members.

**Status:** not started

---

## Grade Calculation

| Points | Grade % | Points | Grade % |
|--------|---------|--------|---------|
| 0      | 0%      | 9      | 56.25%  |
| 1      | 6.25%   | 10     | 62.5%   |
| 2      | 12.5%   | 11     | 68.75%  |
| 3      | 18.75%  | 12     | 75%     |
| 4      | 25%     | 13     | 81.25%  |
| 5      | 31.25%  | 14     | 87.5%   |
| 6      | 37.5%   | 15     | 93.75%  |
| 7      | 43.75%  | ≥16    | 100%    |
| 8      | 50%     |        |         |
