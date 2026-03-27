# Wireframe Comparison: Original Concept vs Current Implementation

> Compares the original project concept (from `docs/original-concept.md` and team brainstorming) with the final implementation state (2026-03-27).

## Feature Comparison

| Feature | Original Concept | Current Implementation | Status |
|---------|-----------------|----------------------|--------|
| **Problem statement** | "Avoid aimless scrolling across streaming platforms" | Personalized movie discovery with ML-based ranking | Adopted |
| **Data source** | TMDB API (free, widely used) | TMDB API v3 + offline tmdb.sqlite (1.17M movies) | Expanded |
| **Tag/genre selection** | "Choose which tags to propose on the app" | 19 TMDB genres as multi-select pills in sidebar | Adopted |
| **Movie matching** | "Match tags entered by users to a movie from the database" | TMDB `discover/movie` API with 8 filter parameters | Expanded |
| **Ranking (cold start)** | "Recommend movies from best to worse TMDB rating" | Popularity-based ordering via TMDB API sort | Adopted |
| **Ranking (personalized)** | Not specified in concept | 10-signal cosine similarity scoring with dynamic weights | New |
| **Already-watched exclusion** | "Remove it from possible recommendations" | Rated + dismissed + watchlisted movies excluded from browse grids | Adopted |
| **Rating system** | "User can give a rating to the movie/series" | 0-100 slider (steps of 10) with color-coded track and sentiment labels | Expanded |
| **Not interested button** | "Replaces the recommendation by another" | "Not interested" dismisses movie and caches details for ML | Adopted |
| **User stats (Spotify Wrapped)** | "How many movies featuring X director or Y actor — accessible anytime" | KPIs, 4 Altair charts, top 5 directors/actors with photos, sortable table | Expanded |
| **Machine learning** | "Can be implemented to support the recommendation system" | Offline pipeline (TF-IDF/SVD, emotion classifier) + online scoring (10 signals) | Expanded |
| **Mood reactions** | Not in original concept | 7 Ekman mood buttons on every rating dialog | New |
| **Watchlist** | Not in original concept | Dedicated page with streaming providers, trailer, Watch Now link | New |
| **Settings page** | Not in original concept | Streaming country, subscriptions, preferred language | New |
| **Keyword search** | Mentioned as "tags" | TMDB keyword autocomplete with removable chips in sidebar | Adopted |
| **Certification filter** | Not in original concept | Age certification dropdown (DE) in sidebar | New |
| **Streaming providers** | Mentioned as "across all streaming platforms" | Provider logos in dialogs + subscription management in Settings | Expanded |
| **Mood filter (Discover)** | Not in original concept | 7 mood pills filtering against precomputed mood_scores.npy | New |
| **Series support** | "Movie/series recommender" | Movies only (series excluded) | Changed |
| **Design/theme** | "Leaving out design stuff for later" | Cinema Gold theme (dark, copper/gold accent, Poppins font) | New |
| **Multi-page navigation** | Not specified | 5 top-navigation tabs (Discover, Rate, Watchlist, Statistics, Settings) | New |

## Summary

| Status | Count | Description |
|--------|-------|-------------|
| Adopted | 6 | Original concept features implemented as described |
| Expanded | 5 | Original ideas implemented with significantly more depth |
| New | 8 | Features not in the original concept |
| Changed | 1 | Series support dropped (movies only) |

The final app goes well beyond the original concept in every dimension: data infrastructure (1.17M movie database vs live API only), ML sophistication (10-signal scoring vs simple tag matching), user interaction (mood reactions, watchlist, settings), and visualization (4 chart types, KPIs, rankings vs basic stats).
