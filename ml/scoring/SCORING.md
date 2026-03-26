# SCORING.md

Personalized scoring system for the movie recommender. Defines how
candidate movies are ranked after TMDB API filtering.

**Created:** 2026-03-26
**Updated:** 2026-03-26

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

   Threshold fallback (mood_filter.py):
     threshold = 0.3
     keep = [m for m in candidates
             if mood_scores[m][selected_mood] > threshold]
     for t in [0.2, 0.1, 0.0]:
         if len(keep) >= 20: break
         threshold = t
         keep = [m for m in candidates
                 if mood_scores[m][selected_mood] > threshold]

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

Only used when sort order is "Personalized Score".

```
final_score(movie) =
    0.25 * keyword_similarity
  + 0.20 * mood_match
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

### Keyword Similarity (0.25)

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

```python
mood_match = mean(candidate_mood_scores[m] for m in selected_moods)
```

If no mood selected: dot product between the user's implicit mood
vector (normalized frequency of mood tags from rating history) and
the candidate's mood scores.

```python
user_implicit_mood = normalized_frequency(all_mood_tags_from_ratings)
mood_match = dot(user_implicit_mood, candidate_mood_scores)
```

**Data source:** `mood_scores.npy` (1.17M x 7)

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

```python
runtime_similarity = 1.0 - abs(user_avg_runtime - candidate_runtime) / 360.0
```

User average runtime is computed from positively-rated movies only
(rating > 50).

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

Negative cosine similarity between the contra vector and the
candidate's keyword vector:

```python
contra_vector = avg(keyword_svd[m] for m in rated_movies if rating <= 30)
contra_penalty = -cosine_sim(contra_vector, candidate_keyword_vector)
```

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

| Rated Films | Keyword | Mood | Director | Actor | Decade | Language | Runtime | Quality | Contra |
|---|---|---|---|---|---|---|---|---|---|
| 0 (cold start) | 0.00 | 0.40 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.60 | 0.00 |
| 1-9 | 0.10 | 0.25 | 0.05 | 0.03 | 0.02 | 0.01 | 0.01 | 0.50 | 0.03 |
| 10-49 | 0.20 | 0.22 | 0.12 | 0.08 | 0.04 | 0.02 | 0.02 | 0.20 | 0.10 |
| 50+ (full) | 0.25 | 0.20 | 0.15 | 0.10 | 0.05 | 0.03 | 0.02 | 0.10 | 0.10 |

All rows sum to 1.00. The transition is smooth -- no hard cutoffs.

---

## User Profile Computation

Recomputed after each new rating. Cached in `user_profile_cache`.

```python
weights = [(rating - 50) / 50 for rating in user_ratings]

user_profile = {
    "keyword_vec":   weighted_avg(keyword_svd[rated_ids], weights),
    "director_vec":  weighted_avg(director_svd[rated_ids], weights),
    "actor_vec":     weighted_avg(actor_svd[rated_ids], weights),
    "decade_vec":    weighted_avg(decade_vec[rated_ids], weights),
    "language_vec":  weighted_avg(language_vec[rated_ids], weights),
    "runtime_pref":  weighted_avg(runtime[rated_ids], positive_weights_only),
    "implicit_mood": normalized_frequency(all_mood_tags),
    "contra_vec":    avg(keyword_svd[ids_where_rating <= 30]),
}
```

---

## Performance

Scoring 300 candidates takes ~50ms on a single CPU core using numpy
vectorized operations. No GPU required. The bottleneck is the TMDB API
calls (~500ms), not the scoring.
