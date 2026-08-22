"""
Index Builder for ML Recommender and Fast Vector Lookups.
Pre-computes TF-IDF vectorizers, SVD latent spaces, and Nearest Neighbor indices.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

logger = logging.getLogger("yorvyn.pipeline.index_builder")


class IndexBuilder:
    """
    Builds and persists ML search matrices, TF-IDF representations,
    and nearest-neighbor similarity graphs.
    """

    def __init__(self, output_dir: Optional[Union[str, Path]] = None):
        self.output_dir = Path(output_dir) if output_dir else Path(__file__).resolve().parents[3] / "models"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_indexes(
        self,
        df: pd.DataFrame,
        save_artifacts: bool = True,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Build and cache vectorizer, SVD, and k-NN index from DataFrame.
        """
        start_time = time.time()
        if df is None or df.empty:
            raise ValueError("Cannot build index on empty DataFrame.")

        # Ensure columns are standardized (notes, accords, description, name, brand)
        from .schema_validator import SchemaValidator
        df = SchemaValidator.standardize_dataframe(df)

        # Construct corpus from combined accords, notes, description, name, and brand
        corpus = []
        for _, row in df.iterrows():
            parts = [
                str(row.get("name", "")),
                str(row.get("brand", "")),
                str(row.get("accords", "")),
                str(row.get("notes", "")),
                str(row.get("description", "")),
            ]
            corpus.append(" ".join(filter(bool, parts)).strip().lower())

        if verbose:
            print(f"   Building TF-IDF vectorizer over {len(corpus):,} fragrance documents...")

        # 1. Fit TF-IDF Vectorizer
        vectorizer = TfidfVectorizer(
            max_features=2500,
            ngram_range=(1, 2),
            stop_words="english",
            sublinear_tf=True
        )
        tfidf_matrix = vectorizer.fit_transform(corpus)

        # 2. Fit SVD for latent semantic indexing
        n_components = min(64, tfidf_matrix.shape[1] - 1) if tfidf_matrix.shape[1] > 10 else 5
        svd = TruncatedSVD(n_components=n_components, random_state=42)
        svd_matrix = svd.fit_transform(tfidf_matrix)

        # 3. Fit Nearest Neighbors
        nn_model = NearestNeighbors(
            n_neighbors=min(50, len(df)),
            metric="cosine",
            algorithm="brute"
        )
        nn_model.fit(tfidf_matrix)

        elapsed = time.time() - start_time
        if verbose:
            print(f"   ✓ ML indexes built successfully in {elapsed:.2f}s (Vocabulary: {len(vectorizer.vocabulary_):,} tokens)")

        artifacts = {
            "vectorizer": vectorizer,
            "svd": svd,
            "svd_matrix": svd_matrix,
            "nn_model": nn_model,
            "vocab_size": len(vectorizer.vocabulary_),
            "total_documents": len(df),
            "build_timestamp": time.time(),
        }

        if save_artifacts:
            model_path = self.output_dir / "perfume_index_bundle.pkl"
            joblib.dump(artifacts, model_path, compress=3)
            if verbose:
                print(f"   💾 Saved ML index bundle to: {model_path}")

        return artifacts
