# PIPELINE

Offline ML pipeline: feature extraction, mood prediction, keyword classification, quality scores. All scripts in `src/ml/`, all source data in `data/source/`, all outputs in `data/models/`.

---

## Pipeline Architecture

```
data/source/tmdb.sqlite (7.7 GB, offline only)
    |
    |  src/ml/features.py
    |  src/ml/moods.py
    |  src/ml/quality.py
    |  src/ml/index.py
    |  src/ml/verify.py
    |  src/ml/classifier.py
    |
    v
data/models/ (~3 GB, shipped to production)
    keyword_svd_vectors.npy     1.17M x 200   float32
    director_svd_vectors.npy    1.17M x 200   float32
    actor_svd_vectors.npy       1.17M x 200   float32
    genre_vectors.npy           1.17M x 19    float32
    decade_vectors.npy          1.17M x 15    float32
    language_vectors.npy        1.17M x 20    float32
    runtime_normalized.npy      1.17M x 1     float32
    mood_scores.npy             1.17M x 7     float32
    quality_scores.npy          1.17M x 1     float32
    movie_id_index.json         1.17M entries
    keyword_mood_map.json       ~70K entries
    keyword_svd.pkl
    director_svd.pkl
    actor_svd.pkl
```

The 7.7 GB database is never queried at runtime. Only the model files
are loaded into memory for scoring.

---

## Stage 1: Feature Extraction

**Script:** `features.py`

**Input:** `data/source/tmdb.sqlite`

Extracts feature matrices from the TMDB database and reduces
high-dimensional sparse features via SVD.

| Feature | Raw Dimensions | Reduced | DB Source |
|---|---|---|---|
| Keyword TF-IDF | 1.17M x 70,779 | 1.17M x 200 (SVD) | `movie_keywords` + `keywords` |
| Genre onehot | 1.17M x 19 | No reduction | `movie_genres` + `genres` |
| Director onehot | 1.17M x ~170K | 1.17M x 200 (SVD) | `movie_crew` WHERE `job = 'Director'` |
| Actor onehot | 1.17M x ~4M | 1.17M x 200 (SVD) | `movie_cast` WHERE `cast_order < 5` |
| Decade onehot | 1.17M x 15 | No reduction | `movies.release_date` -> decade bins (1900s-2020s) |
| Language onehot | 1.17M x 20 | No reduction | `movies.original_language` top-20 by count |
| Runtime normalized | 1.17M x 1 | No reduction | `movies.runtime / 360.0` |

**SVD details:**

- TruncatedSVD with 200 components (pragmatic default from LSA
  literature, configurable via `--svd-components`). Observed explained
  variance: keywords 33.7%, directors 2.8%, actors 1.7%. Low
  director/actor values reflect extreme sparsity (most people appear
  in 1-2 films), not a poor component count.
- Keywords use TF-IDF weighting before SVD
- Directors and actors use binary onehot (present/absent) before SVD
- SVD models saved as `.pkl` for transforming new movies later

**Output:** 7 `.npy` arrays + 3 `.pkl` SVD models + `movie_id_index.json`

---

## Stage 1b: Keyword-to-Mood Classifier

**Script:** `classifier.py`

**Input:** `data/source/labeled_keywords.tsv` + `data/source/tmdb.sqlite`

**Output:** `data/models/keyword_mood_map.json` (~70K entries) + confusion matrix + results CSV

See [Keyword-to-Mood Classification](#keyword-to-mood-classification) below.

---

## Stage 2: Mood Prediction

**Script:** `moods.py`

**Input:** `data/source/tmdb.sqlite` + `data/source/genre_mood_map.json` + `data/models/keyword_mood_map.json`

For each of the 1.17M movies, predicts 7 mood probabilities by combining 4 signals.

---

### Signal 1: Genre → Mood Mapping

19 manual rules mapping each genre to mood weights (independent scores, not normalized to 1.0). Canonical source: `data/source/genre_mood_map.json`.

```
Action          -> {interested: 0.5, afraid: 0.3}
Adventure       -> {happy: 0.4, interested: 0.4, surprised: 0.3}
Animation       -> {happy: 0.5, sad: 0.2, interested: 0.2}
Comedy          -> {happy: 0.8, surprised: 0.2}
Crime           -> {angry: 0.4, interested: 0.4, afraid: 0.2}
Documentary     -> {interested: 0.6, sad: 0.2, angry: 0.1}
Drama           -> {sad: 0.5, interested: 0.4}
Family          -> {happy: 0.5, sad: 0.2}
Fantasy         -> {interested: 0.5, surprised: 0.3, happy: 0.2}
History         -> {interested: 0.6, sad: 0.3, angry: 0.1}
Horror          -> {afraid: 0.7, disgusted: 0.3}
Music           -> {happy: 0.6, interested: 0.3, sad: 0.1}
Mystery         -> {interested: 0.5, surprised: 0.4, afraid: 0.2}
Romance         -> {happy: 0.6, sad: 0.3}
Science Fiction -> {interested: 0.5, surprised: 0.3, afraid: 0.2}
TV Movie        -> {}
Thriller        -> {afraid: 0.5, interested: 0.4, surprised: 0.2}
War             -> {angry: 0.5, sad: 0.5, afraid: 0.2}
Western         -> {interested: 0.4, happy: 0.2, angry: 0.2}
```

For multi-genre movies, mood scores are averaged across genres.

---

### Signal 2: Keyword → Mood Mapping (Supervised Pipeline)

See [Keyword-to-Mood Classification](#keyword-to-mood-classification) below for the full labeling pipeline and classifier details. Output: `data/models/keyword_mood_map.json` (~70K entries).

---

### Signal 3: Emotion Classifier on Overview Text

Pre-trained transformer applied to all movie overviews.

- **Model:** `j-hartmann/emotion-english-distilroberta-base` (runs fully offline via `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, model must be cached locally before pipeline run)
- **Input:** `movies.overview` + `movies.tagline` (concatenated)
- **Output:** 7 classes: `{anger, disgust, fear, joy, neutral, sadness, surprise}`
- **Mapping to 7 moods:** Direct 7-to-7 mapping (see `EMOTION_TO_MOOD` in `moods.py`)

~995K movies have non-empty overviews. The remaining ~179K get mood scores only from genre and keyword signals.

---

### Signal 4: Emotion Classifier on Reviews

Same classifier applied to `movie_reviews.content`. Only 38,535 movies (3.3%) have reviews. Reviews are the most authentic mood signal because viewers describe what they actually felt.

---

### Signal Combination

Dynamic weighting based on availability: reviews-heavy when available (0.50), overview-heavy when no reviews (0.50), genre+keyword fallback when no text. Weights always sum to 1.0. See `moods.py:combine_signals()` for exact weights.

**Output:** `data/models/mood_scores.npy` (1.17M x 7)

---

## Stage 3: Quality Scores

**Script:** `quality.py`

Bayesian average quality score, normalized to [0, 1]. Formula and behavior: see SCORING.md (Quality Score section).

**Output:** `data/models/quality_scores.npy` (1.17M x 1)

---

## Stage 4a: Build Index

**Script:** `index.py`

Saves `data/models/movie_id_index.json` — bidirectional mapping between `movie_id` (TMDB integer ID) and row index (position in `.npy` arrays). Required to look up vectors for movies returned by the TMDB API.

---

## Stage 4b: Verify Pipeline

**Script:** `verify.py`

Verifies all 14 pipeline outputs exist and have consistent row counts against movie_id_index.json. No database access needed.

---

## Running the Pipeline

```bash
# Full pipeline (takes several hours for mood prediction)
python3 src/ml/features.py --db data/source/tmdb.sqlite --output data/models/
python3 src/ml/classifier.py --tsv data/source/labeled_keywords.tsv --db data/source/tmdb.sqlite --output data/models/keyword_mood_map.json
python3 src/ml/moods.py --db data/source/tmdb.sqlite --output data/models/
python3 src/ml/quality.py --db data/source/tmdb.sqlite --output data/models/
python3 src/ml/index.py --db data/source/tmdb.sqlite --output data/models/
python3 src/ml/verify.py --output data/models/
```

Run order: `features` + `quality` (parallel) → `classifier` → `moods` → `index` → `verify`.
Each stage is idempotent and can be re-run independently.

---

## Dependencies

| Package | Purpose |
|---|---|
| `numpy` | Array operations, `.npy` storage |
| `scipy` | Sparse matrices for TF-IDF, SVD |
| `scikit-learn` | TruncatedSVD, TfidfTransformer, classifiers |
| `transformers` | Emotion classifier (Stage 2) |
| `torch` | Backend for transformers |
| `tqdm` | Progress bars |
| `sentence-transformers` | EmbeddingGemma-300M (Stage 1b) |

---

## Memory Requirements

| Stage | Peak RAM |
|---|---|
| Feature extraction (keyword TF-IDF) | ~8 GB (sparse matrix) |
| SVD reduction | ~4 GB |
| Emotion classifier (batched) | ~2 GB (GPU) or ~4 GB (CPU) |
| Final .npy arrays in memory | ~3 GB |

---

## Keyword-to-Mood Classification

---

### Overview

Each of the ~70K TMDB keywords is classified into one or more of 7 mood categories (based on the Ekman model, branded as "TMDB Vibes"):

| Mood | Ekman Basis | Example Keywords |
|------|-------------|-----------------|
| Happy | Joy | comedy, friendship, celebration, wedding |
| Interested | Interest | biography, detective, documentary, science |
| Surprised | Surprise | time travel, plot twist, magic, doppelganger |
| Sad | Sadness | grief, depression, orphan, loneliness |
| Disgusted | Disgust | gore, corruption, exploitation, cannibal |
| Afraid | Fear | horror, ghost, nightmare, serial killer |
| Angry | Anger | revenge, racism, terrorism, oppression |

Keywords can be: **single** (one mood), **multi** (2-3 moods), or **none** (Uncategorized).

---

## Labeling Pipeline

---

### Stage 1: Initial Labeling (Top 5000 Keywords)

File: `data/source/labeled_keywords.tsv`

The top 5000 keywords (by movie_count) were labeled with mood assignments. Each keyword received:
- `assigned_moods`: comma-separated mood list (canonical order: Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry)
- `assignment_type`: single, multi, or none
- `confidence`: high, medium, or low

---

### Stage 2: Manual Review

All 5000 keywords were reviewed against 3 real film overviews per keyword. The review produced **~666 corrections** across 5000 keywords (~13.3% correction rate).

---

### Stage 3: Classifier Training

The single-label subset (1,049 keywords) trains a classifier
(EmbeddingGemma-300M sentence embeddings) that infers moods for the
remaining ~65K unlabeled keywords. See `classifier.py`.

Training uses single-label only for a methodologically clean 7-class
problem. Alternatives considered: multi-label with one-vs-rest (more
data but harder to evaluate with standard metrics).

**Split strategy:** 80/10/10 (train/val/test) via two successive `train_test_split` calls with `stratify` and fixed seed (`random_state=13`). First split: 90% train+val, 10% test. Second split: of the 90%, 87.5% train and 12.5% val (= 10% of total). Follows Assignment 11 Task 1. The validation set serves as the "mock exam" — an overfitting detector (lecture 11 slide 34). The test set is used only once for the final report, never during training or model selection.

**Curse of dimensionality:** KNN struggles in high-dimensional spaces (d > 4) because distance metrics lose discriminative power (lecture 11 slide 9). Our keyword embeddings are 768-dim, which means KNN is expected to underperform compared to linear models (LogisticRegression, SVC). KNN is included for the mandatory course comparison but expected to rank lower.

---

## Distribution (After Review)

---

### Dataset Overview

| Metric | Count | % |
|--------|-------|---|
| Total keywords | 5000 | 100% |
| Categorized (single + multi) | 2683 | 53.7% |
| Uncategorized | 2317 | 46.3% |

| Assignment Type | Count |
|-----------------|-------|
| single | 1049 |
| multi | 1634 |
| none (Uncategorized) | 2317 |

| Confidence | Count |
|------------|-------|
| high | 1518 |
| medium | 2298 |
| low | 1184 |

---

### Single-Label Distribution

The 1049 single-label keywords form the primary training signal:

| Mood | Single-Label Count | % of Single |
|------|--------------------|-------------|
| Interested | 332 | 31.6% |
| Happy | 207 | 19.7% |
| Afraid | 204 | 19.4% |
| Sad | 187 | 17.8% |
| Angry | 52 | 5.0% |
| Surprised | 36 | 3.4% |
| Disgusted | 31 | 3.0% |

Class imbalance is inherent to the TMDB keyword space: very few keywords are *exclusively* surprising, disgusting, or angry without also being fearful, sad, or interesting.

---

### Multi-Label Distribution

The 1634 multi-label keywords have the following mood participation counts:

| Mood | Multi-Label Appearances |
|------|------------------------|
| Afraid | 756 |
| Interested | 713 |
| Sad | 707 |
| Angry | 501 |
| Happy | 347 |
| Disgusted | 221 |
| Surprised | 183 |

---

### Total Distribution (Single + Multi)

| Mood | Total Appearances | Single | Multi |
|------|-------------------|--------|-------|
| Interested | 1045 | 332 | 713 |
| Afraid | 960 | 204 | 756 |
| Sad | 894 | 187 | 707 |
| Happy | 554 | 207 | 347 |
| Angry | 553 | 52 | 501 |
| Disgusted | 252 | 31 | 221 |
| Surprised | 219 | 36 | 183 |

Afraid, Sad, and Interested dominate multi-label assignments because they co-occur with many other moods (war is Sad+Afraid+Angry, horror is Disgusted+Afraid, politics is Interested+Angry).

---

### Top Multi-Label Combinations

| Combination | Count | Typical Keywords |
|-------------|-------|-----------------|
| Interested,Afraid | 260 | thriller, spy, conspiracy, surveillance |
| Happy,Sad | 176 | family relationships, romance, nostalgia |
| Sad,Afraid | 174 | war, disease, disaster, imprisonment |
| Interested,Sad | 127 | immigration, social issues, coming of age |
| Afraid,Angry | 117 | terrorism, kidnapping, gang violence |
| Sad,Angry | 100 | racism, poverty, bullying, betrayal |
| Interested,Angry | 98 | politics, activism, revolution, censorship |
| Happy,Interested | 96 | sports, adventure, music, discovery |
| Interested,Surprised | 93 | sci-fi, surrealism, time travel, alternate reality |
| Disgusted,Afraid | 69 | horror, zombie, slasher, body horror |
| Happy,Surprised | 50 | fairy tale, magic, comedy, circus |
| Sad,Afraid,Angry | 49 | world war, genocide, civil war |
| Disgusted,Angry | 41 | corruption, hate crime, sexism, pollution |
| Sad,Disgusted,Angry | 36 | sexual violence, slavery, child abuse |
| Disgusted,Afraid,Angry | 33 | fascism, torture, massacre, sadism |

---

## Classification Rules

---

### Rule 1: Label the Keyword, Not the Films

The mood label must reflect the **emotional connotation of the keyword itself**, not the accidental genre distribution of the 3 example films. A keyword like "elevator" appears in thrillers (Devil), comedies (Elf), and dramas — the elevator itself carries no emotional weight.

---

### Rule 2: Uncategorized by Default

A keyword stays Uncategorized unless it has a **clear, consistent emotional signal** across typical usage in films. When in doubt, Uncategorized is correct. A false positive (wrong mood label) is worse than a false negative (Uncategorized) for the classifier.

---

### Rule 3: Canonical Multi-Label Order

When a keyword has multiple moods, list them in this fixed order:
```
Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry
```

---

## Mood-Specific Patterns

---

### Happy Indicators

- **Comedy genres:** slapstick, romcom, parody, spoof, dark comedy (+ Surprised)
- **Music/performance:** concert, rock 'n' roll, hip-hop, dance, singing, live music
- **Celebration:** christmas, wedding, holiday, birthday party, carnival
- **Positive relationships:** friendship, female friendship, male friendship
- **Positive emotions:** inspirational, hope, kindness, playful

---

### Interested Indicators

- **Knowledge/discovery:** biography, documentary, investigation, science, history
- **Narrative complexity:** detective, conspiracy, mystery (+ Surprised), espionage
- **Cultural exploration:** samurai, martial arts, archaeology, filmmaking
- **Social themes:** politics (+ Angry), feminism (+ Angry), immigration (+ Sad)

---

### Surprised Indicators (Underrepresented — 36 single-label)

- **Supernatural encounters:** alien (+ Interested, Afraid), time travel (+ Interested)
- **Narrative twists:** plot twist, mistaken identity, doppelganger (+ Afraid)
- **Wonder/magic:** fairy tale (+ Happy), magic (+ Happy), circus (+ Happy)
- **Unconventional forms:** experimental, avant-garde, surrealism (+ Interested)

---

### Sad Indicators

- **Loss/death:** grief, loss of loved one, terminal illness, cancer, suicide
- **Mental health:** depression, loneliness, mental illness, PTSD (+ Afraid)
- **Social suffering:** poverty (+ Angry), homelessness, orphan
- **Historical trauma:** holocaust (+ Disgusted, Angry), slavery (+ Angry)

---

### Disgusted Indicators (Most Underrepresented — 31 single-label)

- **Graphic content:** gore, cannibal, body horror
- **Moral transgression:** corruption (+ Angry), exploitation (+ Angry), incest
- **Systemic abuse:** sexual harassment (+ Angry), child abuse (+ Sad, Angry)
- **Disturbing concepts:** necrophilia, fetish, groper train

---

### Afraid Indicators

- **Horror subgenres:** found footage, slasher, supernatural horror, folk horror
- **Creatures:** vampire, zombie (+ Disgusted), ghost, demon, monster
- **Threats:** serial killer, kidnapping (+ Angry), stalking, home invasion
- **Psychological:** nightmare, paranoia, obsession (+ Interested)

---

### Angry Indicators (Underrepresented — 52 single-label)

- **Injustice:** racism (+ Sad), oppression, censorship, sexism (+ Disgusted)
- **Violence/aggression:** revenge, fight, gang (+ Afraid), terrorism (+ Afraid)
- **Social critique:** satire (+ Happy), punk rock (+ Happy), activism (+ Interested)
- **Political:** dictatorship (+ Afraid), fascism (+ Disgusted, Afraid)

---

## Quality Gradient

Keywords with higher movie_count had better initial labels because the 3 example films were more representative:

| Keyword Range | Avg movie_count | Correction Rate |
|---------------|----------------|-----------------|
| 1-340 | 36K-950 | 4.7% |
| 341-1340 | 950-290 | 11.5% |
| 1341-2340 | 290-160 | 14.4% |
| 2341-3340 | 160-110 | 13.9% |
| 3341-5000 | 110-50 | 15.5% |

---

## Correction Statistics

| Correction Type | Count | Share |
|-----------------|-------|-------|
| False mood → Uncategorized (settings, objects, professions, animals) | ~270 | 40% |
| Relationship keywords → Happy,Sad/multi (consistency rule) | ~160 | 24% |
| Multi → Single (simplification where one mood dominates) | ~130 | 20% |
| Uncategorized → specific mood (emotional keywords missed) | ~106 | 16% |
| **Total corrections** | **~666** | **100%** |

---

## Impact on Classifier Training

The corrections primarily **removed false positives** — keywords incorrectly given emotional labels. This makes the remaining labeled keywords more precise as training data, even though the absolute count decreases.

Net effect on class distribution:
- **Sad and Afraid shrunk** (many settings/objects/professions removed)
- **Uncategorized grew significantly** (2317 of 5000 = 46.3%)
- **Disgusted, Angry, Surprised slightly grew** (targeted additions)
- **Happy stable** (new additions balanced removals)

---

### Addressing Class Imbalance

The single-label imbalance (Interested=332 vs. Disgusted=31) is structural. Mitigation strategies:

1. **Class weights** in the loss function (inversely proportional to class frequency)
2. **Oversampling** of minority classes (Surprised, Disgusted, Angry)
3. **Threshold tuning** per mood at inference time
