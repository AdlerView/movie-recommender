"""ML classification: keyword-to-mood classifier and mood score prediction.

Two pipeline scripts:
- keyword_mood_classifier.py (Stage 1b): Trains on 1,049 manually labeled
  keywords with EmbeddingGemma-300M embeddings, infers moods for 68K+ keywords
- predict_moods.py (Stage 2): Combines 4 signals (genre, keyword, overview
  emotion, review emotion) into per-movie mood scores (1.17M × 7 moods)
"""
from __future__ import annotations
