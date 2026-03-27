"""Statistics page — Dashboard with KPIs, charts, ML evaluation, and ratings table.

Displays aggregated metrics, a sortable table of all rated movies, and
an ML evaluation section with classifier comparison, confusion matrix,
cross-validation, and KNN hyperparameter tuning.

Grading requirements: 3 (Data visualization) + 5 (Machine learning).
"""
from __future__ import annotations

from pathlib import Path

import altair as alt
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from app.utils.db import (
    load_decade_distribution,
    load_genre_distribution,
    load_language_distribution,
    load_mood_distribution,
    load_rated_movies_table,
    load_rating_distribution,
    load_rating_history,
    load_stats_summary,
    load_top_actors,
    load_top_directors,
    load_user_vs_tmdb,
)
from app.utils.tmdb import poster_url

st.header("Your statistics", divider="gray", text_alignment="center")

# --- Load aggregated data from SQLite ---
stats = load_stats_summary()

# --- Empty state ---
if stats["rated_count"] == 0 and stats["watchlisted_count"] == 0:
    st.info(
        "Start discovering and rating movies to see your statistics here!",
        icon=":material/bar_chart:",
    )
    st.stop()

# --- KPI metrics row ---
# Watch hours and average runtime from cached movie_details.runtime
total_hours = stats["total_runtime_min"] / 60

with st.container(horizontal=True):
    st.metric(
        "Watch hours",
        f"{total_hours:.1f}h",
        border=True,
    )
    st.metric(
        "Avg runtime",
        f"{stats['avg_runtime_min']} min",
        border=True,
    )
    st.metric("Rated", stats["rated_count"], border=True)
    st.metric(
        "Avg rating",
        f"{stats['avg_rating']:.0f} / 100",
        border=True,
    )

with st.container(horizontal=True):
    st.metric("Watchlisted", stats["watchlisted_count"], border=True)
    st.metric("Dismissed", stats["dismissed_count"], border=True)

# --- Genre distribution bar chart ---
genre_data = load_genre_distribution()

if genre_data:
    st.subheader("Genre distribution", divider="gray")
    # Build DataFrame — SQL already returns rows sorted by count descending
    genre_df = pd.DataFrame(genre_data, columns=["Genre", "Movies"])
    # Altair horizontal bar chart with explicit sort by frequency descending
    chart = alt.Chart(genre_df).mark_bar().encode(
        x=alt.X("Movies:Q", title="Movies"),
        y=alt.Y("Genre:N", sort="-x", title=None),
    )
    st.altair_chart(chart, use_container_width=True)

# --- Language distribution bar chart ---
lang_data = load_language_distribution()

if lang_data:
    st.subheader("Language distribution", divider="gray")
    lang_df = pd.DataFrame(lang_data, columns=["Language", "Movies"])
    chart = alt.Chart(lang_df).mark_bar().encode(
        x=alt.X("Movies:Q", title="Movies"),
        y=alt.Y("Language:N", sort="-x", title=None),
    )
    st.altair_chart(chart, use_container_width=True)

# --- Decade distribution bar chart ---
decade_data = load_decade_distribution()

if decade_data:
    st.subheader("Decade distribution", divider="gray")
    decade_df = pd.DataFrame(decade_data, columns=["Decade", "Movies"])
    # Explicit categorical order to preserve descending decade sort
    chart = alt.Chart(decade_df).mark_bar().encode(
        x=alt.X("Movies:Q", title="Movies"),
        y=alt.Y("Decade:N", sort=list(decade_df["Decade"]), title=None),
    )
    st.altair_chart(chart, use_container_width=True)

# --- Top directors ---
directors = load_top_directors()

if directors:
    st.subheader("Favorite directors", divider="gray")
    for rank, (name, count) in enumerate(directors, start=1):
        # Display as numbered list with movie count
        suffix = "movie" if count == 1 else "movies"
        st.markdown(f"**{rank}. {name}** — {count} {suffix}")

# --- User vs TMDB scatter plot ---
user_vs_tmdb = load_user_vs_tmdb()

if user_vs_tmdb:
    st.subheader("Your rating vs TMDB", divider="gray")
    scatter_df = pd.DataFrame(user_vs_tmdb, columns=["TMDB", "You", "Title"])
    # Scale TMDB 0-10 to 0-100 for comparable axes
    scatter_df["TMDB (scaled)"] = scatter_df["TMDB"] * 10
    # Diagonal reference line: points above = you rate higher than TMDB
    line_df = pd.DataFrame({"x": [0, 100], "y": [0, 100]})
    base_line = alt.Chart(line_df).mark_line(
        strokeDash=[4, 4], color="gray", opacity=0.5,
    ).encode(x="x:Q", y="y:Q")
    points = alt.Chart(scatter_df).mark_circle(size=60).encode(
        x=alt.X("TMDB (scaled):Q", title="TMDB rating (scaled to 100)", scale=alt.Scale(domain=[0, 100])),
        y=alt.Y("You:Q", title="Your rating", scale=alt.Scale(domain=[0, 100])),
        tooltip=["Title", "TMDB", "You"],
    )
    st.altair_chart(base_line + points, use_container_width=True)

# --- Rating distribution histogram ---
rating_values = load_rating_distribution()

if rating_values:
    st.subheader("Rating distribution", divider="gray")
    rating_df = pd.DataFrame({"Rating": rating_values})
    # Histogram with bins at each step of 10 (0-10, 10-20, ..., 90-100)
    chart = alt.Chart(rating_df).mark_bar().encode(
        x=alt.X("Rating:Q", bin=alt.Bin(step=10), title="Rating (0-100)"),
        y=alt.Y("count()", title="Movies"),
    )
    st.altair_chart(chart, use_container_width=True)

# --- Rating history line chart ---
rating_history = load_rating_history()

if len(rating_history) >= 2:
    st.subheader("Rating history", divider="gray")
    history_df = pd.DataFrame(rating_history, columns=["Date", "Rating"])
    history_df["Date"] = pd.to_datetime(history_df["Date"])
    # Add sequential index for x-axis (movie #1, #2, ...) since multiple
    # ratings may share the same timestamp
    history_df["Movie #"] = range(1, len(history_df) + 1)
    chart = alt.Chart(history_df).mark_line(point=True).encode(
        x=alt.X("Movie #:Q", title="Movie #"),
        y=alt.Y("Rating:Q", title="Rating", scale=alt.Scale(domain=[0, 100])),
        tooltip=["Movie #", "Rating", "Date"],
    )
    st.altair_chart(chart, use_container_width=True)

# --- Mood distribution bar chart ---
mood_data = load_mood_distribution()

if mood_data:
    st.subheader("Mood distribution", divider="gray")
    mood_df = pd.DataFrame(mood_data, columns=["Mood", "Reactions"])
    chart = alt.Chart(mood_df).mark_bar().encode(
        x=alt.X("Reactions:Q", title="Reactions"),
        y=alt.Y("Mood:N", sort="-x", title=None),
    )
    st.altair_chart(chart, use_container_width=True)

# --- ML Evaluation (Course Requirement 5) ---
# Keyword-to-mood classification evaluation. Uses precomputed results
# from ml/classification/keyword_mood_classifier.py (Phase 1b) + live cross-validation
# and KNN hyperparameter tuning via ml/evaluation/ml_eval.py.
st.subheader("ML Evaluation: Keyword-to-Mood", divider="gray")

_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "output"
_eval_results_path = _OUTPUT_DIR / "keyword_classifier_results.csv"
_eval_cm_path = _OUTPUT_DIR / "keyword_classifier_confusion_matrix.png"

if _eval_results_path.exists():
    # Classifier comparison table (from Phase 1b pipeline output)
    _results_df = pd.read_csv(_eval_results_path)
    st.caption("**Classifier comparison** (scaled + unscaled, train + validation)")
    st.dataframe(_results_df, hide_index=True, use_container_width=True)

    # Best model KPIs
    _scaled_non_dummy = _results_df[
        (~_results_df["Classifier"].str.startswith("Dummy"))
        & (_results_df["Scaling"] == "Scaled")
    ].sort_values("Val F1", ascending=False)
    if not _scaled_non_dummy.empty:
        _best = _scaled_non_dummy.iloc[0]
        with st.container(horizontal=True):
            st.metric("Best classifier", _best["Classifier"], border=True)
            st.metric("Val Accuracy", f"{_best['Val Acc']:.1%}", border=True)
            st.metric("Val F1 (macro)", f"{_best['Val F1']:.4f}", border=True)
            # Overfitting indicator: train-val gap
            _gap = _best["Train F1"] - _best["Val F1"]
            st.metric(
                "Train-Val Gap",
                f"{_gap:.4f}",
                delta=f"{'Overfitting' if _gap > 0.15 else 'OK'}",
                delta_color="inverse" if _gap > 0.15 else "off",
                border=True,
            )

    # Confusion matrix (saved as PNG by pipeline)
    if _eval_cm_path.exists():
        st.caption("**Confusion matrix** (best model on test set)")
        st.image(str(_eval_cm_path), use_container_width=True)

    # Cross-validation + KNN tuning (live, cached)
    if st.button("Run cross-validation & KNN tuning", icon=":material/science:"):
        import numpy as np
        from sklearn.preprocessing import LabelEncoder, RobustScaler

        from ml.evaluation import knn_hyperparameter_plot, run_cross_validation

        # Load keyword data and embeddings (same as pipeline)
        _tsv_path = (
            Path(__file__).resolve().parent.parent.parent
            / "data" / "input"
            / "tmdb-keyword-frequencies_labeled_top5000.tsv"
        )
        if _tsv_path.exists():
            with st.spinner("Generating embeddings and running evaluation..."):
                _labeled = pd.read_csv(_tsv_path, sep="\t")
                _single = _labeled[_labeled["assignment_type"] == "single"]
                _keywords = _single["keyword_name"].tolist()
                _labels = _single["assigned_moods"].tolist()

                # Generate embeddings (cached by sentence-transformers)
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer("google/embeddinggemma-300m")
                _embeddings = _model.encode(_keywords, show_progress_bar=False,
                                            normalize_embeddings=True)

                # Encode labels and split
                _le = LabelEncoder()
                _y = _le.fit_transform(_labels)
                from sklearn.model_selection import train_test_split
                _x_tv, _x_test, _y_tv, _y_test = train_test_split(
                    _embeddings, _y, test_size=0.10, stratify=_y, random_state=13,
                )
                _x_train, _x_val, _y_train, _y_val = train_test_split(
                    _x_tv, _y_tv, test_size=0.125, stratify=_y_tv, random_state=13,
                )

                # Scale
                _scaler = RobustScaler()
                _x_train_s = _scaler.fit_transform(_x_train)
                _x_val_s = _scaler.transform(_x_val)
                _x_all_s = _scaler.fit_transform(_embeddings)

                # Cross-validation (10-fold, Notebook 10-1 pattern)
                _best_name = _scaled_non_dummy.iloc[0]["Classifier"] if not _scaled_non_dummy.empty else "MLPClassifier"
                from ml.evaluation import get_classifiers
                _classifiers = get_classifiers()
                _best_clf = _classifiers.get(_best_name, _classifiers["MLPClassifier"])
                _cv_scores = run_cross_validation(_best_clf, _x_all_s, _y)

                st.caption(f"**10-fold cross-validation** ({_best_name})")
                with st.container(horizontal=True):
                    st.metric("Mean accuracy", f"{_cv_scores.mean():.1%}", border=True)
                    st.metric("Std", f"± {_cv_scores.std():.1%}", border=True)

                # KNN hyperparameter tuning (k=1..20, Notebook 10-1 pattern)
                _k_fig = knn_hyperparameter_plot(
                    _x_train_s, _x_val_s, _y_train, _y_val,
                )
                st.caption("**KNN hyperparameter tuning** (k=1..20)")
                st.pyplot(_k_fig)
                plt.close(_k_fig)
        else:
            st.warning("Labeled keyword data not found.", icon=":material/warning:")
else:
    st.info(
        "Run `python3 ml/classification/keyword_mood_classifier.py` to generate "
        "evaluation results.",
        icon=":material/science:",
    )

# --- Top actors ---
actors = load_top_actors()

if actors:
    st.subheader("Favorite actors", divider="gray")
    for rank, (name, count) in enumerate(actors, start=1):
        # Display as numbered list with movie count
        suffix = "movie" if count == 1 else "movies"
        st.markdown(f"**{rank}. {name}** — {count} {suffix}")

# --- Rated movies table ---
# Compact sortable table with thumbnail, title, duration, and ratings.
rated_rows = load_rated_movies_table()

if rated_rows:
    st.subheader("Your ratings", divider="gray")

    # Build DataFrame with display-ready columns
    table_data = []
    for row in rated_rows:
        # Format runtime as "Xh Ymin"
        runtime = row.get("runtime")
        if runtime:
            h, m = divmod(runtime, 60)
            duration = f"{h}h {m}min" if h else f"{m} min"
        else:
            duration = "—"

        table_data.append({
            "Poster": poster_url(row.get("poster_path"), size="w92") or "",
            "Title": row.get("title") or f"Movie #{row['movie_id']}",
            "Duration": duration,
            "TMDB": round(row["vote_average"], 1) if row.get("vote_average") is not None else None,
            "Your rating": row["rating"],
        })

    df = pd.DataFrame(table_data)

    # Sortable interactive dataframe with poster thumbnails
    st.dataframe(
        df,
        column_config={
            "Poster": st.column_config.ImageColumn("", width="small"),
            "Title": st.column_config.TextColumn("Title"),
            "Duration": st.column_config.TextColumn("Duration"),
            "TMDB": st.column_config.NumberColumn("TMDB", format="%.1f", width="small"),
            "Your rating": st.column_config.NumberColumn(
                "Your rating", format="%d", width="small",
            ),
        },
        hide_index=True,
        use_container_width=True,
        row_height=50,
    )
