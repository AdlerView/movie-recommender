# SCORING.md

Personalized scoring system for the movie recommender. Defines how
candidate movies are ranked after TMDB API filtering.

---

## Overview

The TMDB `discover/movie` API handles all hard filters (genre,
certification, year, language, runtime, vote score, vote count,
keywords, streaming providers). The scoring system only handles
what the API cannot: **mood filtering** and **personalized ranking**.

---

## Request Flow

```
User clicks "Discover"
    |
    v
1. TMDB API: discover/movie with all filters
   -> ~100-500 candidate movie IDs + basic data
    |
    v
2. Mood filter (local, only if user selected a mood)
   For each candidate: mood_scores.npy[movie_id_index[id]]
   Keep only movies where selected mood > threshold
   -> ~50-300 candidates

   Threshold fallback: starts at 0.3, steps down to 0.2 → 0.1 → 0.0
   if fewer than 20 candidates pass. See `mood.py`.

   If no mood selected, no mood filtering occurs. The user's
   implicit mood from rating history still influences the
   personalized scoring (see Mood Match component below).
    |
    v
3. Scoring depends on selected sort order:

   | Sort Option             | TMDB sort_by              | ML Scoring |
   |-------------------------|---------------------------|------------|
   | Personalized (default)  | popularity.desc           | Yes (full) |
   | Popularity              | popularity.desc           | No         |
   | Rating                  | vote_average.desc         | No         |
   | Release Date            | primary_release_date.desc | No         |

   For "Personalized", API sorts by popularity (reasonable candidate
   pool), then local scoring re-ranks. Other options use API order.
   Mood filter from step 2 applies to ALL sort orders.
    |
    v
4. Sort + return top-20
   Display data from discover response + mood scores from npy
```

---

## Scoring Formula

Only used when sort order is "Personalized".

```
final_score(movie) =
    0.20 * keyword_similarity
  + 0.20 * mood_match
  + 0.05 * genre_similarity
  + 0.15 * director_similarity
  + 0.10 * actor_similarity
  + 0.05 * decade_similarity
  + 0.03 * language_similarity
  + 0.02 * runtime_similarity
  + 0.10 * quality_score
  + 0.10 * contra_penalty
  -----
  = 1.00
```

---

## Component Details

---

### Keyword Similarity (0.20)

Cosine similarity between the user's keyword preference vector and
the candidate's keyword vector. The user vector is a weighted average
of keyword SVD vectors from all rated movies, where the weight is the
normalized rating: `(rating - 50) / 50`. A rating of 100 gives weight
+1.0, rating 0 gives -1.0, rating 50 gives 0.0.

**What it captures:** "User likes movies about plot twists, psychology,
dark humor" -- learned implicitly from rated movies without the user
ever stating it.

**Data source:** `keyword_svd_vectors.npy` (1.17M x 200)

---

### Mood Match (0.20)

If the user selected a mood explicitly: average of the candidate's
predicted mood scores for the selected moods.

If no mood selected: dot product between the user's implicit mood
vector (normalized frequency of mood tags from rating history) and
the candidate's mood scores.

**Data source:** `mood_scores.npy` (1.17M x 7)

---

### Genre Similarity (0.05)

Cosine similarity between the user's genre preference vector and the
candidate's genre multi-hot vector. The user vector is a weighted average
of genre vectors from all rated movies (same weight formula as keywords).

**What it captures:** "User prefers Action + Thriller over Romance +
Comedy" — learned from genre distributions of rated films. Complements
keyword similarity which operates at a finer thematic level.

**Data source:** `genre_vectors.npy` (1.17M x 19, multi-hot)

---

### Director Similarity (0.15)

Same logic as keyword similarity but using director SVD vectors.

**What it captures:** "User likes Fincher" automatically boosts
Villeneuve and Nolan because their director vectors are nearby in the
reduced space (they direct similar types of movies).

**Data source:** `director_svd_vectors.npy` (1.17M x 200), built from
`movie_crew` WHERE `job = 'Director'`

---

### Actor Similarity (0.10)

Same logic using actor SVD vectors. Only top-5 cast per film (by
`cast_order`) to reduce noise from extras and minor roles.

**Data source:** `actor_svd_vectors.npy` (1.17M x 200), built from
`movie_cast` WHERE `cast_order < 5`

---

### Decade Similarity (0.05)

Cosine similarity between user's decade preference (weighted average
of decade onehot vectors from rated movies) and candidate's decade.

**What it captures:** "User prefers 90s and 2000s films over classics."

**Data source:** `decade_vectors.npy` (1.17M x 15), bins from 1900s
to 2020s

---

### Language Similarity (0.03)

Same logic using language onehot vectors for the top-20 languages by
movie count.

**What it captures:** "User watches mostly English and Korean films."

**Data source:** `language_vectors.npy` (1.17M x 20), from
`movies.original_language`

---

### Runtime Similarity (0.02)

1 minus absolute distance between user's average runtime preference
and candidate runtime, both normalized to [0, 1]. User average
computed from positively-rated movies only (rating > 50).

**What it captures:** "User avoids 3-hour epics" or "User prefers
longer films."

**Data source:** `runtime_normalized.npy` (1.17M x 1), from
`movies.runtime / 360.0`

---

### Quality Score (0.10)

Bayesian average, precomputed:

```
m = median(all_vote_counts)
C = mean(all_vote_averages)
quality = (vote_count * vote_avg + m * C) / (vote_count + m)
```

Normalized to [0, 1]. Prevents movies with 1 vote and 10.0 average
from ranking above well-established films.

**Data source:** `quality_scores.npy` (1.17M x 1)

---

### Contra Penalty (0.10)

Negative cosine similarity between the contra vector (average keyword
SVD of disliked movies) and the candidate's keyword vector.

**What it captures:** demotes movies thematically similar to movies the
user rated poorly. If a user gave 10/100 to romantic comedies, other
romantic comedies get penalized.

Sources for the contra vector:
- Movies with ratings at or below 30/100 (ratings 0-30)
- Dismissed movies ("not interested") — treated as negative signal

Threshold alternatives considered: below 60 (too aggressive, includes
lukewarm "Decent" ratings), tunable parameter (deferred complexity).
Dismiss alternatives considered: cosmetic only (simpler but loses
useful signal), immediate implementation (rejected — Phase 0 should
not depend on scoring.py).

**Data source:** `keyword_svd_vectors.npy` + `user_ratings`

---

## Dynamic Weights by Rating Count

The scoring weights shift based on how many movies the user has rated.
With few ratings, quality (objective film quality) dominates. With many
ratings, personalization (keyword, director, actor preferences)
dominates.

| Rated Films | Keyword | Mood | Genre | Director | Actor | Decade | Language | Runtime | Quality | Contra |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 (cold start) | 0.00 | 0.40 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.60 | 0.00 |
| 1-9 | 0.08 | 0.25 | 0.02 | 0.05 | 0.03 | 0.02 | 0.01 | 0.01 | 0.50 | 0.03 |
| 10-49 | 0.16 | 0.22 | 0.04 | 0.12 | 0.08 | 0.04 | 0.02 | 0.02 | 0.20 | 0.10 |
| 50+ (full) | 0.20 | 0.20 | 0.05 | 0.15 | 0.10 | 0.05 | 0.03 | 0.02 | 0.10 | 0.10 |

All rows sum to 1.00. The transition is smooth -- no hard cutoffs.

---

## User Profile Computation

Recomputed when input data changes. Cached in `user_profile_cache` with an MD5 fingerprint over ratings + mood reactions + dismissed set. Re-ratings, mood tag changes, and new dismissals all trigger recomputation.

**Rating weight formula:** `(rating - 50) / 50` maps the 0-100 scale to [-1.0, +1.0]. A rating of 100 = +1.0 (strong positive), 50 = 0.0 (neutral), 0 = -1.0 (strong negative). The weighted average thus captures both what the user likes and dislikes.

**Input signals:**

| Signal | Source | Weight |
|---|---|---|
| Rated movies | `user_ratings` | `(rating - 50) / 50` per movie |
| Watchlisted movies | `watchlist` (not yet rated) | +0.3 (equivalent to rating 65 — interested but unconfirmed) |
| Dismissed movies | `dismissed` + ratings ≤ 30 | Contribute to contra vector (average of keyword SVD vectors) |
| Mood reactions | `user_rating_moods` | Normalized frequency distribution (implicit mood vector) |

**Runtime and popularity preferences** are computed from positively-rated movies only (rating > 50).

---

## Performance

Scoring 300 candidates takes ~8ms on a single CPU core using numpy
vectorized operations. No GPU required. The bottleneck is the TMDB API
calls (~500ms), not the scoring.
