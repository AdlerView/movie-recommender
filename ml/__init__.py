"""ML pipeline for personalized movie recommendations.

This package contains the complete machine learning system in 4 subpackages:

- extraction: Offline feature extraction from tmdb.sqlite into .npy arrays
  (TF-IDF, SVD dimensionality reduction, Bayesian quality scores)
- classification: Keyword-to-mood classifier training + mood score prediction
  (7 Ekman moods, 4 combined signals, 1.17M movies)
- scoring: Online scoring at request time (10-signal cosine similarity,
  dynamic weight shifting, user profile computation, mood filter)
- evaluation: Academic ML evaluation functions (classifier comparison,
  cross-validation, KNN tuning) + Jupyter notebook

The offline pipeline runs once to generate ~3 GB of .npy arrays from the
7.7 GB tmdb.sqlite database. The online scoring module loads these arrays
as a lazy singleton and scores candidates in ~8ms per 300 movies.
"""
from __future__ import annotations
