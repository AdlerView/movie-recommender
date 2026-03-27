"""Offline feature extraction from tmdb.sqlite into .npy arrays.

Pipeline stages 1, 3, and 4 live here. Stage 2 (mood prediction) is in
ml/classification/ because it depends on the keyword-to-mood classifier.

Stage 1 (extract_features.py): 7 feature vectors via TF-IDF + SVD
Stage 3 (quality_scores.py): Bayesian average quality scores
Stage 4 (build_index.py): movie_id ↔ row_index mapping + verification
"""
from __future__ import annotations
