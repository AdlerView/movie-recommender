# Keyword-to-Mood Classification

This document describes the mood classification system for TMDB keywords, the labeling methodology, and the patterns discovered during manual review.

---

## Overview

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

### Stage 1: Initial Labeling (Top 5000 Keywords)

File: `data/tmdb-keyword-frequencies_labeled_top5000.tsv`

The top 5000 keywords (by movie_count) were labeled with mood assignments. Each keyword received:
- `assigned_moods`: comma-separated mood list (canonical order: Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry)
- `assignment_type`: single, multi, or none
- `confidence`: high, medium, or low

### Stage 2: Manual Review (This Session)

All 5000 keywords were reviewed against 3 real film overviews per keyword (from `data/tmdb-keyword-frequencies_labeled_top5000_with_movies.tsv`). The review produced **~666 corrections** across 5000 keywords (~13.3% correction rate).

### Stage 3: Classifier Training

The single-label subset of labeled keywords trains a classifier (EmbeddingGemma-300M sentence embeddings) that infers moods for the remaining ~65K unlabeled keywords. See `pipeline/keyword_mood_classifier.py`.

---

## Distribution (After Review)

### Overview

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

### Single-Label Distribution

The 1049 single-label keywords form the primary training signal for the classifier:

| Mood | Single-Label Count | % of Single |
|------|--------------------|-------------|
| Interested | 332 | 31.6% |
| Happy | 207 | 19.7% |
| Afraid | 204 | 19.4% |
| Sad | 187 | 17.8% |
| Angry | 52 | 5.0% |
| Surprised | 36 | 3.4% |
| Disgusted | 31 | 3.0% |

Class imbalance is inherent to the TMDB keyword space: very few keywords are *exclusively* surprising, disgusting, or angry without also being fearful, sad, or interesting. These three moods appear primarily in multi-label combinations.

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

### Rule 1: Label the Keyword, Not the Films

The mood label must reflect the **emotional connotation of the keyword itself**, not the accidental genre distribution of the 3 example films. A keyword like "elevator" appears in thrillers (Devil), comedies (Elf), and dramas — the elevator itself carries no emotional weight.

### Rule 2: Uncategorized by Default

A keyword stays Uncategorized unless it has a **clear, consistent emotional signal** across typical usage in films. When in doubt, Uncategorized is correct. A false positive (wrong mood label) is worse than a false negative (Uncategorized) for the classifier.

### Rule 3: Canonical Multi-Label Order

When a keyword has multiple moods, list them in this fixed order:
```
Happy, Interested, Surprised, Sad, Disgusted, Afraid, Angry
```

---

## Keyword Categories and Their Mood Patterns

### Always Uncategorized

These keyword categories **never** receive a mood label because they describe **how** or **where**, not **what emotion**:

| Category | Examples | Rationale |
|----------|----------|-----------|
| Geographic locations | paris, tokyo, berlin, arctic, australia | Setting, no inherent emotion |
| Time periods | 1920s, 1950s, victorian england, feudal japan | Temporal context, not emotion |
| Source material | based on novel, based on comic, adaptation | Production metadata |
| Film format/technique | 3d, stop motion, CGI, arthouse, found footage | Production method |
| Professions (neutral) | doctor, lawyer, teacher, nurse, photographer | Role descriptor |
| Animals (neutral) | wolf, lion, snake, crocodile, gorilla, rat | Species, not emotion |
| Objects/props | car, diamond, ring, telephone, sword | Physical item |
| Demographics | teenager, young woman, boy, old man | Age/gender descriptor |
| Nationalities/ethnicities | korean, french, african, indigenous | Cultural identity |

### Always Happy,Sad/multi (Relationship Keywords)

**Every keyword describing a human relationship** receives Happy,Sad/multi. Relationships in film are inherently bipolar — they evoke both love/joy and loss/pain.

**~50+ keywords follow this rule:**

- **Family:** father, mother, daughter, siblings, brother, sisters, grandparent-grandchild, aunt-niece, in-laws, single mother, single father, family relationships, parent-child
- **Romantic:** couple, dating, lovers, newlywed, engaged couple, boyfriend, husband, ex-boyfriend, ex-wife, one-night stand, soulmates, friends to lovers, lovesickness
- **Specific:** interracial romance, gay couple, gay romance, polyamory, open relationship, platonic love, co-workers relationship, man-woman relationship

**Exception — Loss keywords stay Sad/single:** death of husband, death of brother, dead mother, orphan, widow. When the relationship partner is dead, the Happy component is absent.

**Exception — Conflict keywords stay Sad,Angry/multi:** love triangle, infidelity, adultery, divorce, jealousy, betrayal. When the relationship is defined by conflict, Angry replaces or supplements Happy.

### Direct Emotion Words: Usually Correct

Keywords that **directly name an emotion** are almost always correctly labeled:

| Correctly labeled | Mood |
|-------------------|------|
| hilarious, joyous, celebratory, playful | Happy |
| melancholy, depressing, lonely, hopeless | Sad |
| disgusting, grotesque, repulsive | Disgusted |
| terrifying, ominous, paranoid | Afraid |
| hostile, scathing, oppression | Angry |
| bewildered, incredulous | Surprised |
| thoughtful, philosophical | Interested |

**Common valence errors found during review:**

| Keyword | Wrong Label | Correct Label | Why |
|---------|------------|---------------|-----|
| embarrassed | Sad | Surprised | Embarrassment = unexpected situation |
| frantic | Afraid,Angry | Afraid | Panic = fear, not anger |
| wistful | Happy,Sad | Sad | Wistfulness = pure melancholy |
| noise | Angry | Afraid | Sounds as threat (A Quiet Place) |
| hypochondriac | Sad | Afraid | Defined by fear of illness |
| conceited | Angry | Disgusted | Arrogance = contempt/disgust |

---

## Mood-Specific Patterns

### Happy Indicators

Keywords that reliably signal Happy:
- **Comedy genres:** slapstick, romcom, parody, spoof, dark comedy (+ Surprised)
- **Music/performance:** concert, rock 'n' roll, hip-hop, dance, singing, live music
- **Celebration:** christmas, wedding, holiday, birthday party, carnival
- **Positive relationships:** friendship, female friendship, male friendship
- **Positive emotions:** inspirational, hope, kindness, playful

### Interested Indicators

Keywords that reliably signal Interested:
- **Knowledge/discovery:** biography, documentary, investigation, science, history
- **Narrative complexity:** detective, conspiracy, mystery (+ Surprised), espionage
- **Cultural exploration:** samurai, martial arts, archaeology, filmmaking
- **Social themes:** politics (+ Angry), feminism (+ Angry), immigration (+ Sad)

### Surprised Indicators (Underrepresented — 36 single-label)

Keywords that reliably signal Surprised:
- **Supernatural encounters:** alien (+ Interested, Afraid), time travel (+ Interested)
- **Narrative twists:** plot twist, mistaken identity, doppelganger (+ Afraid)
- **Wonder/magic:** fairy tale (+ Happy), magic (+ Happy), circus (+ Happy)
- **Unconventional forms:** experimental, avant-garde, surrealism (+ Interested)

### Sad Indicators

Keywords that reliably signal Sad:
- **Loss/death:** grief, loss of loved one, terminal illness, cancer, suicide
- **Mental health:** depression, loneliness, mental illness, PTSD (+ Afraid)
- **Social suffering:** poverty (+ Angry), homelessness, orphan
- **Historical trauma:** holocaust (+ Disgusted, Angry), slavery (+ Angry)

### Disgusted Indicators (Most Underrepresented — 31 single-label)

Keywords that reliably signal Disgusted:
- **Graphic content:** gore, cannibal, body horror
- **Moral transgression:** corruption (+ Angry), exploitation (+ Angry), incest
- **Systemic abuse:** sexual harassment (+ Angry), child abuse (+ Sad, Angry)
- **Disturbing concepts:** necrophilia, fetish, groper train

### Afraid Indicators

Keywords that reliably signal Afraid:
- **Horror subgenres:** found footage, slasher, supernatural horror, folk horror
- **Creatures:** vampire, zombie (+ Disgusted), ghost, demon, monster
- **Threats:** serial killer, kidnapping (+ Angry), stalking, home invasion
- **Psychological:** nightmare, paranoia, obsession (+ Interested)

### Angry Indicators (Underrepresented — 52 single-label)

Keywords that reliably signal Angry:
- **Injustice:** racism (+ Sad), oppression, censorship, sexism (+ Disgusted)
- **Violence/aggression:** revenge, fight, gang (+ Afraid), terrorism (+ Afraid)
- **Social critique:** satire (+ Happy), punk rock (+ Happy), activism (+ Interested)
- **Political:** dictatorship (+ Afraid), fascism (+ Disgusted, Afraid)

---

## Quality Gradient

Keywords with higher movie_count (more frequently used in TMDB) had better initial labels because the 3 example films were more representative. Keywords with movie_count < 200 had a ~16-18% correction rate vs. ~5% for the top keywords.

| Keyword Range | Avg movie_count | Correction Rate |
|---------------|----------------|-----------------|
| 1–340 | 36K–950 | 4.7% |
| 341–1340 | 950–290 | 11.5% |
| 1341–2340 | 290–160 | 14.4% |
| 2341–3340 | 160–110 | 13.9% |
| 3341–5000 | 110–50 | 15.5% |

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

The corrections primarily **removed false positives** — keywords that were incorrectly given emotional labels (settings, professions, animals, formats). This makes the remaining labeled keywords more precise as training data for the sentence-embedding classifier, even though the absolute number of labeled keywords decreases.

The net effect on class distribution:
- **Sad and Afraid shrunk** (many settings/objects/professions removed)
- **Uncategorized grew significantly** (2317 of 5000 = 46.3%)
- **Disgusted, Angry, Surprised slightly grew** (targeted additions of legitimately emotional keywords)
- **Happy stable** (new additions balanced removals)

### Addressing Class Imbalance

The single-label class imbalance (Interested=332 vs. Disgusted=31) is structural, not a labeling failure. Mitigation strategies for classifier training:

1. **Class weights** in the loss function (inversely proportional to class frequency)
2. **Oversampling** of minority classes (Surprised, Disgusted, Angry)
3. **Multi-label training** alongside single-label — the 1634 multi-label keywords provide additional signal for underrepresented moods (Disgusted appears in 221 multi-label keywords despite only 31 single-label)
4. **Threshold tuning** per mood at inference time

---

## Navigation

- **Parent:** [CLAUDE.md](../CLAUDE.md)
- **ML Pipeline:** [ML-PIPELINE.md](ML-PIPELINE.md)
- **Labeled data:** `data/tmdb-keyword-frequencies_labeled_top5000.tsv`
- **Classifier:** `pipeline/keyword_mood_classifier.py`
