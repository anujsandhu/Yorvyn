"""
Advanced perfume recommender runtime.

The runtime is intentionally local-first:
1. Use pre-trained classical ML models for almost every request
2. Use multiple ranking signals so results are faster and more stable
3. Call Gemini/OpenAI only when local confidence is very low
"""

from __future__ import annotations

import os
import re
import time
import warnings
from dataclasses import dataclass
from functools import reduce
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union, cast
import operator

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances, linear_kernel
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from .config import settings
from .pipeline.dataset_manager import dataset_manager

warnings.filterwarnings("ignore")

_ftax = dataset_manager.fragrance_taxonomy

TEXT_STOPWORDS = set(_ftax.get("stopwords", [
    # Generic filler words
    "a", "an", "and", "are", "as", "at", "be", "best", "but", "by", "for",
    "from", "have", "i", "in", "is", "it", "its", "like", "me", "my", "of",
    "on", "or", "perfume", "please", "recommend", "recommendation", "scent",
    "something", "that", "the", "this", "to", "want", "with", "would",
    "fragrance", "looking", "wear", "smell", "get", "give", "need", "find",
    "good", "great", "nice", "any", "some", "one", "can", "you", "us",
    # Relationship words (should not become notes)
    "brother", "sister", "husband", "wife", "boyfriend", "girlfriend",
    "father", "mother", "dad", "mom", "son", "daughter", "friend",
    "broth", "husb", "boyfri", "girlfri",  # tokenized fragments
    # Occasion words (handled separately, not notes)
    "wedding", "office", "party", "date", "night", "daily", "gym",
    "outdoor", "casual", "formal", "work", "occasion", "event",
    # Descriptor words that aren't notes
    "strong", "light", "heavy", "mild", "subtle", "intense", "bold",
    "long", "lasting", "longevity", "projection", "sillage",
    "premium", "luxury", "expensive", "cheap", "affordable", "budget",
    "new", "old", "classic", "modern", "popular", "famous", "brand",
]))
NEGATION_TOKENS = {"avoid", "dislike", "dont", "don't", "hate", "no", "not", "without"}
NOISE_TITLE_TOKENS = set(_ftax.get("noise_title_tokens", [
    "sample", "samples", "sampler", "vial", "vials", "decant", "mini", "minis",
    "lot", "tester", "testers", "ml", "bottle", "bottles", "spray", "sealed",
    "set", "gift", "pack", "bundle", "empty",
]))
_raw_syns = _ftax.get("note_synonyms", {})
if _raw_syns:
    NOTE_SYNONYMS = {k: tuple(v) for k, v in _raw_syns.items()}
else:
    NOTE_SYNONYMS = {
        "aquatic": ("aquatic", "marine", "fresh", "water"),
        "citrusy": ("citrus", "bergamot", "lemon", "orange"),
        "floral": ("floral", "rose", "jasmine", "white floral"),
        "sweet": ("sweet", "vanilla", "caramel", "gourmand"),
        "woody": ("woody", "cedar", "sandalwood", "vetiver"),
        "oud": ("oud", "woody", "smoky", "amber"),
        "spicy": ("spicy", "cinnamon", "pepper", "cardamom"),
        "fresh": ("fresh", "clean", "green", "citrus"),
        "powdery": ("powdery", "musk", "iris", "soft"),
    }

_raw_occ = _ftax.get("occasion_hints", {})
if _raw_occ:
    OCCASION_HINTS = {k: tuple(v) for k, v in _raw_occ.items()}
else:
    OCCASION_HINTS = {
        "office":  ("fresh", "clean", "green", "citrus", "musk", "aromatic", "light"),
        "work":    ("fresh", "clean", "green", "citrus", "musk", "aromatic", "light"),
        "daily":   ("fresh", "clean", "soft", "citrus", "aromatic", "light", "musk"),
        "date":    ("rose", "vanilla", "amber", "musk", "sweet", "sensual", "warm", "seductive"),
        "night":   ("amber", "oud", "vanilla", "spicy", "woody", "dark", "intense"),
        "party":   ("amber", "oud", "sweet", "spicy", "woody", "bold", "intense"),
        "wedding": ("rose", "white floral", "musk", "vanilla", "elegant", "woody", "spicy", "amber", "patchouli"),
        "gym":     ("fresh", "aquatic", "clean", "citrus", "sport", "light"),
        "outdoor": ("green", "woody", "fresh", "earthy", "citrus", "aromatic"),
        "casual":  ("fresh", "clean", "light", "citrus", "soft", "musk"),
        "formal":  ("woody", "amber", "spicy", "elegant", "musk", "leather"),
    }

_raw_seas = _ftax.get("season_hints", {})
if _raw_seas:
    SEASON_HINTS = {k: tuple(v) for k, v in _raw_seas.items()}
else:
    SEASON_HINTS = {
        "summer":  ("citrus", "aquatic", "fresh", "green", "light", "ozonic"),
        "spring":  ("floral", "fresh", "green", "citrus", "light", "rose"),
        "winter":  ("amber", "vanilla", "oud", "spicy", "woody", "warm", "patchouli"),
        "autumn":  ("woody", "amber", "spicy", "earthy", "leather", "vetiver"),
        "fall":    ("woody", "amber", "spicy", "earthy", "leather", "vetiver"),
        "monsoon": ("fresh", "green", "woody", "clean", "earthy"),
    }

_raw_mood = _ftax.get("mood_hints", {})
if _raw_mood:
    MOOD_HINTS = {k: tuple(v) for k, v in _raw_mood.items()}
else:
    MOOD_HINTS = {
        "romantic":   ("rose", "vanilla", "musk", "amber", "sweet"),
        "confident":  ("woody", "spicy", "amber", "leather", "oud"),
        "luxury":     ("oud", "amber", "iris", "woody", "leather"),
        "playful":    ("fruity", "sweet", "floral", "fresh", "citrus"),
        "calm":       ("soft", "powdery", "musk", "clean", "lavender"),
        "mysterious": ("oud", "amber", "smoky", "dark", "incense"),
        "energetic":  ("citrus", "fresh", "aquatic", "green", "sport"),
    }


def clean_accords(raw: Any) -> str:
    """Convert raw accord data into clean, searchable text."""
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return ""
    cleaned = re.sub(r"[\[\]'\"{}()]", " ", str(raw))
    cleaned = cleaned.replace(",", " ")
    return " ".join(cleaned.split()).lower()


def normalize_text(raw: Any) -> str:
    text = clean_accords(raw)
    text = re.sub(r"[^a-z0-9\s/-]", " ", text)
    text = text.replace("/", " ")
    return " ".join(text.split()).strip()


def tokenize_text(raw: Any) -> list[str]:
    normalized = normalize_text(raw)
    return [token for token in normalized.split() if len(token) > 1]


def clamp(value: Union[float, np.ndarray], low: float = 0.0, high: float = 1.0) -> Union[float, np.ndarray]:
    if isinstance(value, np.ndarray):
        return np.clip(value, low, high)
    return float(max(low, min(high, value)))


def dedupe_terms(terms: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for term in terms:
        token = normalize_text(term)
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return tuple(ordered)


def top_indices(scores: np.ndarray, limit: int) -> np.ndarray:
    if limit <= 0 or scores.size == 0:
        return np.array([], dtype=int)
    k = min(limit, scores.size)
    if k == scores.size:
        idx = np.argsort(scores)
        return idx[::-1]
    idx = np.argpartition(scores, -k)[-k:]
    return idx[np.argsort(scores[idx])[::-1]]


def normalize_gender(value: Any) -> str:
    text = normalize_text(value)
    if "unisex" in text or "both" in text or "women and men" in text:
        return "unisex"
    if "women" in text or "female" in text or "lady" in text:
        return "women"
    if "men" in text or "male" in text or "gent" in text:
        return "men"
    return "unisex"


@dataclass(frozen=True)
class PreferenceProfile:
    raw_text: str
    gender: str = ""
    occasion: str = ""
    season: str = ""
    mood: str = ""
    liked_notes: tuple[str, ...] = ()
    disliked_notes: tuple[str, ...] = ()
    reference_perfumes: tuple[str, ...] = ()
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    expanded_terms: tuple[str, ...] = ()
    source: str = "local"

    @property
    def all_positive_terms(self) -> tuple[str, ...]:
        base_terms = list(self.liked_notes)
        base_terms.extend(self.expanded_terms)
        for ref in self.reference_perfumes:
            base_terms.extend(tokenize_text(ref))
        return dedupe_terms(base_terms)

    @property
    def query_text(self) -> str:
        parts = [self.raw_text.strip()]
        if self.reference_perfumes:
            parts.append(" ".join(self.reference_perfumes))
        if self.liked_notes:
            parts.append(" ".join(self.liked_notes))
        if self.expanded_terms:
            parts.append(" ".join(self.expanded_terms))
        if self.gender:
            parts.append(self.gender)
        return " ".join(part for part in parts if part).strip()


class AdvancedPerfumeRecommender:
    """Local-first perfume recommender with multi-signal ranking."""

    _models_trained = False

    def __init__(
        self,
        project_root: Optional[Union[str, Path]] = None,
        autoload: bool = True,
        **_: Any,
    ):
        self.data: Optional[pd.DataFrame] = None
        self.tfidf_vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self.kmeans_model: Optional[MiniBatchKMeans] = None
        self.svd_model: Optional[TruncatedSVD] = None
        self.knn_model: Optional[NearestNeighbors] = None
        self.knn_svd_reducer: Optional[TruncatedSVD] = None
        self.knn_reduced = None
        self.rf_scorer: Optional[HistGradientBoostingRegressor] = None
        self.rf_svd_reducer: Optional[TruncatedSVD] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_matrix = None
        self.encoded_features = None
        self.training_metadata: dict[str, Any] = {}

        self.search_corpus = pd.Series(dtype=str)
        self.dataset_tokens: list[set[str]] = []
        self.accord_tokens: list[set[str]] = []
        self.name_brand_tokens: list[set[str]] = []
        self.keyword_to_indices: dict[str, list[int]] = {}
        self.id_to_index: dict[int, int] = {}
        self.dataset_gender = np.array([], dtype=object)
        self.quality_scores = np.array([], dtype=np.float32)
        self.popularity_scores = np.array([], dtype=np.float32)
        self.title_penalties = np.array([], dtype=np.float32)
        self.source_strength = np.array([], dtype=np.float32)
        self.svd_embeddings = None
        self.svd_row_norms = None

        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent.parent
        self.project_root = Path(project_root)
        self.models_dir = self.project_root / "models"
        self.data_dir = self.project_root / "data"

        if not autoload:
            return

        self.initialize()

    def initialize(self) -> bool:
        start_time = time.time()
        if self._load_pretrained_models():
            self._prepare_runtime_artifacts()
            elapsed = time.time() - start_time
            print(f"⚡ All pre-trained models loaded in {elapsed:.2f}s")
            self.__class__._models_trained = True
            return True

        print("⚠ Pre-trained models not found — training from scratch…")
        self._load_all_datasets()
        if self.data is not None and len(self.data) > 1:
            self._train_all_models()
            self.__class__._models_trained = True
            print(f"   Startup completed in {time.time() - start_time:.2f}s")
            return True
        else:
            print("❌ No data available for training")
            print(f"   Startup completed in {time.time() - start_time:.2f}s")
            return False

    # ------------------------------------------------------------------
    # Model loading and training
    # ------------------------------------------------------------------

    def _load_pretrained_models(self) -> bool:
        required = [
            "tfidf_vectorizer",
            "tfidf_matrix",
            "kmeans_model",
            "svd_model",
            "knn_model",
            "knn_svd_reducer",
            "knn_reduced",
            "scaler",
            "feature_matrix",
            "perfume_dataset",
            "training_metadata",
        ]
        for name in required:
            if not (self.models_dir / f"{name}.pkl").exists():
                print(f"   Missing model file: {name}.pkl")
                return False

        try:
            print("📦 Loading pre-trained models…")
            self.data = joblib.load(self.models_dir / "perfume_dataset.pkl")
            self.tfidf_vectorizer = joblib.load(self.models_dir / "tfidf_vectorizer.pkl")
            self.tfidf_matrix = joblib.load(self.models_dir / "tfidf_matrix.pkl")
            self.kmeans_model = joblib.load(self.models_dir / "kmeans_model.pkl")
            self.svd_model = joblib.load(self.models_dir / "svd_model.pkl")
            self.knn_model = joblib.load(self.models_dir / "knn_model.pkl")
            self.knn_svd_reducer = joblib.load(self.models_dir / "knn_svd_reducer.pkl")
            self.knn_reduced = joblib.load(self.models_dir / "knn_reduced.pkl")
            self.scaler = joblib.load(self.models_dir / "scaler.pkl")
            self.feature_matrix = joblib.load(self.models_dir / "feature_matrix.pkl")
            self.encoded_features = self.feature_matrix
            self.training_metadata = joblib.load(self.models_dir / "training_metadata.pkl")

            optional = {
                "rf_scorer": "rf_scorer.pkl",
                "rf_svd_reducer": "rf_svd_reducer.pkl",
            }
            for attr, filename in optional.items():
                path = self.models_dir / filename
                if path.exists():
                    setattr(self, attr, joblib.load(path))

            if self.data is not None and "accords" in self.data.columns:
                self.data["accords"] = self.data["accords"].apply(clean_accords)

            meta = self.training_metadata
            print(f"   ✓ Dataset:    {len(self.data) if self.data is not None else 0:,} perfumes")
            print(f"   ✓ TF-IDF:     {self.tfidf_matrix.shape[1] if self.tfidf_matrix is not None else '?'} features")
            print(f"   ✓ K-Means:    {meta.get('n_clusters', '?')} clusters")
            print(f"   ✓ SVD:        {meta.get('svd_components', '?')} components")
            print(f"   ✓ KNN:        {meta.get('knn_neighbors', '?')} neighbors")
            print(f"   ✓ Version:    {meta.get('version', '1.0')}")
            return True
        except Exception as exc:
            print(f"   ❌ Failed to load models: {exc}")
            return False

    def _load_all_datasets(self):
        master_path = self.data_dir / "master_perfume_catalog.csv"
        if master_path.exists():
            try:
                df = self._read_csv(master_path)
                df["dataset_source"] = "master_catalog"
                self.data = self._merge_datasets([df])
                print(f"   ✓ Loaded master catalog: {len(self.data):,} perfumes")
                return
            except Exception as exc:
                print(f"   ✗ Failed to load master catalog: {exc}")

        datasets = {
            "fra_perfumes": self.data_dir / "fra_perfumes.csv",
            "final_perfume_data": self.data_dir / "final_perfume_data.csv",
            "ebay_mens": self.data_dir / "ebay_mens_perfume.csv",
            "ebay_womens": self.data_dir / "ebay_womens_perfume.csv",
        }
        all_data = []
        for name, path in datasets.items():
            if not path.exists():
                continue
            try:
                df = self._read_csv(path)
                df["dataset_source"] = name
                all_data.append(df)
                print(f"   ✓ Loaded {name}: {len(df):,} rows")
            except Exception as exc:
                print(f"   ✗ Failed to load {name}: {exc}")

        if all_data:
            self.data = self._merge_datasets(all_data)
            print(f"   ✓ Merged dataset: {len(self.data):,} perfumes")

    @staticmethod
    def _read_csv(path: Path) -> pd.DataFrame:
        for encoding in ("utf-8", "latin-1", "iso-8859-1", "cp1252"):
            try:
                return pd.read_csv(path, encoding=encoding)
            except Exception:
                continue
        raise RuntimeError(f"Cannot read {path}")

    def _merge_datasets(self, datasets: list[pd.DataFrame]) -> pd.DataFrame:
        merged_frames = []
        for df in datasets:
            standardized = {
                "name": self._col(df, ["Name", "name", "title"], "Unknown"),
                "brand": self._col(df, ["Brand", "brand"], "Unknown"),
                "gender": self._col(df, ["Gender", "gender"], "unisex").apply(normalize_gender),
                "description": self._col(df, ["Description", "description"], ""),
                "accords": self._col(df, ["Main Accords", "Notes", "family", "type"], ""),
                "url": self._col(df, ["url", "URL"], ""),
                "image_url": self._col(df, ["Image URL", "image_url"], ""),
                "source": df.get("dataset_source", "unknown"),
            }
            standardized["rating"] = pd.to_numeric(
                self._col(df, ["Rating Value", "Rating", "rating"], 4.0),
                errors="coerce",
            ).fillna(4.0)  # type: ignore
            standardized["price"] = pd.to_numeric(
                self._col(df, ["Price", "price"], 0),
                errors="coerce",
            ).fillna(0)  # type: ignore
            standardized["sold"] = pd.to_numeric(
                self._col(df, ["sold"], 0),
                errors="coerce",
            ).fillna(0)  # type: ignore
            standardized["rating_count"] = pd.to_numeric(
                self._col(df, ["Rating Count", "rating_count"], 0).astype(str).str.replace(",", "", regex=False),
                errors="coerce",
            ).fillna(0)  # type: ignore

            frame = pd.DataFrame(standardized)
            frame["accords"] = frame["accords"].apply(clean_accords)
            merged_frames.append(frame)

        result = pd.concat(merged_frames, ignore_index=True)
        result["name"] = result["name"].astype(str).str.strip()
        result["brand"] = result["brand"].astype(str).str.strip()
        result.drop_duplicates(subset=["name", "brand"], keep="first", inplace=True)
        result.reset_index(drop=True, inplace=True)
        result["id"] = range(len(result))
        return result

    @staticmethod
    def _col(df: pd.DataFrame, names: Sequence[str], default: Any = "") -> pd.Series:
        for column in names:
            if column in df.columns:
                return df[column]
        return pd.Series([default] * len(df))

    def _extract_column(self, df: pd.DataFrame, names: Sequence[str], default: Any = "") -> pd.Series:
        """Backwards-compatible alias used by older tests/scripts."""
        return self._col(df, names, default)

    def _train_all_models(self):
        """Backwards-compatible alias used by older tests/scripts."""
        self._train_fallback()
        self._prepare_runtime_artifacts()
        self.__class__._models_trained = True

    def _train_fallback(self):
        if self.data is None or len(self.data) == 0:
            return

        print("\n📚 Training essential ML models…\n")
        training_data = self.data.copy()
        if len(training_data) > 10000:
            training_data = training_data.sample(n=10000, random_state=42)
        training_data = training_data.reset_index(drop=True)
        training_data["id"] = range(len(training_data))
        self.data = training_data.copy()

        combined_text = (
            training_data["name"].astype(str) + " "
            + training_data["brand"].astype(str) + " "
            + training_data["accords"].astype(str) + " "
            + training_data["description"].astype(str).str[:200]
        )

        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=2000,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95,
            sublinear_tf=True,
            dtype=np.float32,
        )
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(combined_text)

        sample_count = len(training_data)
        cluster_count = max(1, min(40, sample_count // 2 if sample_count < 20 else sample_count // 150))
        self.kmeans_model = MiniBatchKMeans(
            n_clusters=cluster_count,
            random_state=42,
            n_init=3,
            batch_size=max(64, min(1024, sample_count)),
        )
        self.kmeans_model.fit(self.tfidf_matrix)

        assert self.tfidf_matrix is not None, "tfidf_matrix must be set"
        max_svd_components = max(
            1,
            min(100, self.tfidf_matrix.shape[0] - 1, self.tfidf_matrix.shape[1] - 1),
        )
        self.svd_model = TruncatedSVD(
            n_components=max_svd_components,
            random_state=42,
            n_iter=7,
        )
        self.svd_model.fit(self.tfidf_matrix)

        knn_components = max(
            1,
            min(60, self.tfidf_matrix.shape[0] - 1, self.tfidf_matrix.shape[1] - 1),
        )
        self.knn_svd_reducer = TruncatedSVD(n_components=knn_components, random_state=42)
        self.knn_reduced = self.knn_svd_reducer.fit_transform(self.tfidf_matrix)
        self.knn_model = NearestNeighbors(
            n_neighbors=max(1, min(25, sample_count)),
            metric="cosine",
            algorithm="brute",
            n_jobs=-1,
        )
        self.knn_model.fit(self.knn_reduced)

        rating_norm = training_data["rating"].fillna(0).to_numpy(dtype=np.float32) / 5.0
        price_log = np.log1p(training_data["price"].fillna(0).to_numpy(dtype=np.float32))
        price_norm = price_log / (float(price_log.max()) + 1e-8)
        sold_log = np.log1p(training_data["sold"].fillna(0).to_numpy(dtype=np.float32))
        sold_norm = sold_log / (float(sold_log.max()) + 1e-8)
        rating_count_log = np.log1p(training_data["rating_count"].fillna(0).to_numpy(dtype=np.float32))
        rating_count_norm = rating_count_log / (float(rating_count_log.max()) + 1e-8)
        desc_len = training_data["description"].fillna("").astype(str).str.len().clip(0, 400).to_numpy(dtype=np.float32) / 400.0

        numeric = np.column_stack([rating_norm, price_norm, sold_norm, rating_count_norm, desc_len])
        self.scaler = StandardScaler()
        self.encoded_features = self.scaler.fit_transform(numeric)
        self.feature_matrix = self.encoded_features
        print("   ✅ Fallback training complete!\n")

    # ------------------------------------------------------------------
    # Runtime preparation
    # ------------------------------------------------------------------

    def _prepare_runtime_artifacts(self):
        if self.data is None:
            self.search_corpus = pd.Series(dtype=str)
            self.dataset_tokens = []
            self.accord_tokens = []
            self.name_brand_tokens = []
            self.keyword_to_indices = {}
            self.id_to_index = {}
            self.dataset_gender = np.array([], dtype=object)
            self.quality_scores = np.array([], dtype=np.float32)
            self.popularity_scores = np.array([], dtype=np.float32)
            self.title_penalties = np.array([], dtype=np.float32)
            self.source_strength = np.array([], dtype=np.float32)
            self.svd_embeddings = None
            self.svd_row_norms = None
            return

        if len(self.data) == 0:
            self.search_corpus = pd.Series(dtype=str)
            self.dataset_tokens = []
            self.accord_tokens = []
            self.name_brand_tokens = []
            self.keyword_to_indices = {}
            self.id_to_index = {}
            self.dataset_gender = np.array([], dtype=object)
            self.quality_scores = np.array([], dtype=np.float32)
            self.popularity_scores = np.array([], dtype=np.float32)
            self.title_penalties = np.array([], dtype=np.float32)
            self.source_strength = np.array([], dtype=np.float32)
            self.svd_embeddings = None
            self.svd_row_norms = None
            return

        # Type guard: cast to DataFrame after both None and empty checks
        self.data = cast(pd.DataFrame, self.data)
        self.data = self.data.copy().reset_index(drop=True)
        self.data["accords"] = self.data["accords"].apply(clean_accords)  # type: ignore
        self.data["name"] = self.data["name"].fillna("").astype(str).str.strip()  # type: ignore
        self.data["brand"] = self.data["brand"].fillna("").astype(str).str.strip()  # type: ignore
        self.data["description"] = self.data["description"].fillna("").astype(str)  # type: ignore
        self.data["gender"] = self.data["gender"].fillna("unisex").apply(normalize_gender)  # type: ignore
        if "id" not in self.data.columns:  # type: ignore
            self.data["id"] = range(len(self.data))  # type: ignore

        # ── Derive image_url from Fragrantica URL if missing ──────────
        # Pattern: https://www.fragrantica.com/perfume/Brand/Name-12345.html
        # Image:   https://fimgs.net/mdimg/perfume/375x500.12345.jpg
        def _fra_img(row: Any) -> str:
            existing = str(row.get("image_url", "") or "")
            if existing and len(existing) > 10:
                return existing
            fra_url = str(row.get("url", "") or "")
            if fra_url and "fragrantica.com" in fra_url:
                m = re.search(r"-(\d+)\.html$", fra_url)
                if m:
                    return f"https://fimgs.net/mdimg/perfume/375x500.{m.group(1)}.jpg"
            return existing

        self.data["image_url"] = self.data.apply(_fra_img, axis=1)  # type: ignore

        combined = (
            self.data["name"].astype(str)  # type: ignore
            + " "
            + self.data["brand"].astype(str)  # type: ignore
            + " "
            + self.data["accords"].astype(str)  # type: ignore
            + " "
            + self.data["description"].astype(str).str[:220]  # type: ignore
        )
        self.search_corpus = combined.apply(normalize_text)
        self.dataset_tokens = [set(tokenize_text(text)) for text in self.search_corpus]
        self.accord_tokens = [set(tokenize_text(text)) for text in self.data["accords"].fillna("")]  # type: ignore
        self.name_brand_tokens = [
            set(tokenize_text(f"{row['name']} {row['brand']}")) for _, row in self.data[["name", "brand"]].iterrows()  # type: ignore
        ]

        self.keyword_to_indices = {}
        for idx, token_set in enumerate(self.accord_tokens):
            for token in token_set:
                self.keyword_to_indices.setdefault(token, []).append(idx)
        for idx, token_set in enumerate(self.name_brand_tokens):
            for token in token_set:
                self.keyword_to_indices.setdefault(token, []).append(idx)

        self.id_to_index = {}
        for idx, perfume_id in enumerate(self.data["id"].tolist()):  # type: ignore
            try:
                self.id_to_index[int(perfume_id)] = idx
            except Exception:
                continue

        ratings = pd.to_numeric(
            self.data["rating"] if self.data is not None and "rating" in self.data.columns else pd.Series(0),  # type: ignore
            errors="coerce"
        ).fillna(0).to_numpy(dtype=np.float32)  # type: ignore
        rating_count = pd.to_numeric(
            self.data["rating_count"] if self.data is not None and "rating_count" in self.data.columns else pd.Series(0),  # type: ignore
            errors="coerce"
        ).fillna(0).to_numpy(dtype=np.float32)  # type: ignore
        sold = pd.to_numeric(
            self.data["sold"] if self.data is not None and "sold" in self.data.columns else pd.Series(0),  # type: ignore
            errors="coerce"
        ).fillna(0).to_numpy(dtype=np.float32)  # type: ignore
        desc_len = (self.data["description"] if self.data is not None else pd.Series("")).astype(str).str.len().clip(0, 400).to_numpy(dtype=np.float32)  # type: ignore
        sources = (self.data["source"] if self.data is not None and "source" in self.data.columns else pd.Series("unknown")).astype(str).str.lower()  # type: ignore

        rating_norm = np.clip(ratings / 5.0, 0.0, 1.0)
        rating_count_log = np.log1p(rating_count)
        rating_count_norm = rating_count_log / (float(rating_count_log.max()) + 1e-8)
        sold_log = np.log1p(sold)
        sold_norm = sold_log / (float(sold_log.max()) + 1e-8)
        desc_norm = desc_len / 400.0

        self.source_strength = np.array(
            [
                1.0 if "fragrantica" in src or "fra" in src
                else 0.92 if "curated" in src or "final" in src
                else 0.76 if "ebay" in src
                else 0.85
                for src in sources
            ],
            dtype=np.float32,
        )

        self.quality_scores = np.array(
            [
                clamp(
                    0.45 * rating_norm[i]
                    + 0.22 * rating_count_norm[i]
                    + 0.15 * sold_norm[i]
                    + 0.08 * desc_norm[i]
                    + 0.10 * self.source_strength[i]
                )
                for i in range(len(self.data))  # type: ignore
            ],
            dtype=np.float32,
        )
        self.popularity_scores = np.array(
            [
                clamp(
                    0.55 * rating_norm[i]
                    + 0.30 * rating_count_norm[i]
                    + 0.15 * sold_norm[i]
                )
                for i in range(len(self.data))  # type: ignore
            ],
            dtype=np.float32,
        )
        self.title_penalties = np.array(
            [
                self._compute_title_penalty(self.data.iloc[i]["name"], sources.iloc[i])  # type: ignore
                for i in range(len(self.data))  # type: ignore
            ],
            dtype=np.float32,
        )
        self.dataset_gender = self.data["gender"].astype(str).to_numpy(dtype=object)  # type: ignore

        self.svd_embeddings = None
        self.svd_row_norms = None
        if self.svd_model is not None and self.tfidf_matrix is not None:
            try:
                self.svd_embeddings = self.svd_model.transform(self.tfidf_matrix).astype(np.float32)
                self.svd_row_norms = np.linalg.norm(self.svd_embeddings, axis=1).astype(np.float32)
            except Exception:
                self.svd_embeddings = None
                self.svd_row_norms = None

    def _compute_title_penalty(self, name: str, source: str) -> float:
        tokens = tokenize_text(name)
        noise_hits = sum(token in NOISE_TITLE_TOKENS for token in tokens)
        penalty = 0.06 * noise_hits          # ↑ from 0.04 — stronger per-token penalty
        if source.startswith("ebay") and noise_hits:
            penalty += 0.08                  # ↑ from 0.05 — eBay samplers penalised harder
        if len(tokens) > 12:
            penalty += 0.04                  # ↑ from 0.03 — very long titles are usually kits
        # Extra penalty for obvious sampler/tester patterns
        name_lower = name.lower()
        if any(p in name_lower for p in ("sample set", "tester set", "gift set", "variety pack", "discovery set")):
            penalty += 0.15
        return float(clamp(penalty, 0.0, 0.50))  # ↑ max from 0.35 to 0.50

    def _resolve_index(self, perfume_id: Union[int, str]) -> Optional[int]:
        if self.data is None or len(self.data) == 0:
            return None
        try:
            numeric_id = int(perfume_id)
        except (TypeError, ValueError):
            return None

        direct = self.id_to_index.get(numeric_id)
        if direct is not None:
            return direct
        if 0 <= numeric_id < len(self.data):
            return int(numeric_id)
        return None

    # ------------------------------------------------------------------
    # Recommendation algorithms
    # ------------------------------------------------------------------

    def _safe_row(self, idx: int) -> dict[str, Any]:
        if self.data is None:
            return {}
        row = self.data.iloc[idx]
        return {
            "id": int(row.get("id", idx)),
            "name": str(row.get("name", "Unknown")),
            "brand": str(row.get("brand", "Unknown")),
            "gender": normalize_gender(row.get("gender", "unisex")),
            "rating": float(row.get("rating", 4.0) or 4.0),
            "accords": clean_accords(row.get("accords", "")),
            "description": str(row.get("description", ""))[:320],
            "image_url": str(row.get("image_url", "")) or "",
            "url": str(row.get("url", "")) or "",
            "price": float(row.get("price", 0) or 0),
            "rating_count": int(row.get("rating_count", 0) or 0),
            "sold": int(row.get("sold", 0) or 0),
            "source": str(row.get("source", "unknown")),
        }

    def recommend_content_based(self, perfume_id: int, limit: int = 10) -> List[Dict]:
        idx = self._resolve_index(perfume_id)
        if idx is None or self.tfidf_matrix is None:
            return []
        try:
            similarities = linear_kernel(self.tfidf_matrix[idx], self.tfidf_matrix).ravel()  # type: ignore
            similarities[idx] = -np.inf
            results = []
            for rec_idx in top_indices(similarities, limit):
                if not np.isfinite(similarities[rec_idx]):
                    continue
                row = self._safe_row(int(rec_idx))
                row["similarity_score"] = float(similarities[rec_idx])
                row["algorithm"] = "content_based"
                results.append(row)
            return results
        except Exception as exc:
            print(f"Error in content-based: {exc}")
            return []

    def recommend_cluster_based(self, perfume_id: int, limit: int = 10) -> List[Dict]:
        idx = self._resolve_index(perfume_id)
        if idx is None or self.kmeans_model is None or self.tfidf_matrix is None:
            return []
        try:
            cluster_id = self.kmeans_model.predict(self.tfidf_matrix[idx])[0]  # type: ignore
            members = np.where(self.kmeans_model.labels_ == cluster_id)[0]
            if members.size == 0:
                return []
            similarities = linear_kernel(self.tfidf_matrix[idx], self.tfidf_matrix[members]).ravel()  # type: ignore
            results = []
            for local_rank in top_indices(similarities, min(limit + 1, members.size)):
                rec_idx = int(members[local_rank])
                if rec_idx == idx:
                    continue
                row = self._safe_row(rec_idx)
                row["similarity_score"] = float(similarities[local_rank])
                row["cluster_match"] = True
                row["algorithm"] = "cluster_based"
                results.append(row)
                if len(results) >= limit:
                    break
            return results
        except Exception as exc:
            print(f"Error in cluster-based: {exc}")
            return []

    def recommend_knn(self, perfume_id: int, limit: int = 10) -> List[Dict]:
        idx = self._resolve_index(perfume_id)
        if idx is None or self.knn_model is None or self.knn_reduced is None:
            return []
        try:
            query = self.knn_reduced[idx:idx + 1]
            neighbor_count = min(limit + 1, getattr(self.knn_model, "n_neighbors", limit + 1))
            distances, indices = self.knn_model.kneighbors(query, n_neighbors=neighbor_count)
            results = []
            for distance, rec_idx in zip(distances[0], indices[0]):
                if int(rec_idx) == idx:
                    continue
                row = self._safe_row(int(rec_idx))
                row["distance"] = float(distance)
                row["similarity_score"] = float(1.0 - distance)
                row["algorithm"] = "knn"
                results.append(row)
                if len(results) >= limit:
                    break
            return results
        except Exception as exc:
            print(f"Error in KNN: {exc}")
            return []

    def recommend_hybrid(
        self,
        perfume_id: int,
        limit: int = 10,
        weights: Optional[dict[str, float]] = None,
    ) -> List[Dict]:
        idx = self._resolve_index(perfume_id)
        if idx is None or self.data is None or len(self.data) == 0:
            return []
        if weights is None:
            weights = {"content": 0.42, "cluster": 0.10, "knn": 0.25, "features": 0.13, "quality": 0.10}

        candidate_scores = np.zeros(len(self.data), dtype=np.float32)

        try:
            if self.tfidf_matrix is not None:
                content_scores = linear_kernel(self.tfidf_matrix[idx], self.tfidf_matrix).ravel().astype(np.float32)  # type: ignore
                candidate_scores += content_scores * weights.get("content", 0.0)
            else:
                content_scores = np.zeros(len(self.data), dtype=np.float32)

            if self.kmeans_model is not None and self.tfidf_matrix is not None:
                cluster_id = self.kmeans_model.predict(self.tfidf_matrix[idx])[0]  # type: ignore
                candidate_scores += (self.kmeans_model.labels_ == cluster_id).astype(np.float32) * weights.get("cluster", 0.0)

            if self.knn_model is not None and self.knn_reduced is not None:
                neighbor_count = min(max(limit * 4, 12), getattr(self.knn_model, "n_neighbors", limit * 4))
                distances, indices = self.knn_model.kneighbors(self.knn_reduced[idx:idx + 1], n_neighbors=neighbor_count)
                for distance, rec_idx in zip(distances[0], indices[0]):
                    candidate_scores[int(rec_idx)] += float(1.0 - distance) * weights.get("knn", 0.0)

            if self.encoded_features is not None and idx < len(self.encoded_features):
                feature_distances = euclidean_distances(
                    np.array([self.encoded_features[idx]]), 
                    self.encoded_features
                )[0]  # type: ignore
                feature_scores = (1.0 / (1.0 + feature_distances)).astype(np.float32)
                candidate_scores += feature_scores * weights.get("features", 0.0)

            if self.quality_scores.size == len(candidate_scores):
                candidate_scores += self.quality_scores * weights.get("quality", 0.0)
                candidate_scores += self.popularity_scores * 0.04
                candidate_scores -= self.title_penalties * 0.12

            candidate_scores[idx] = -np.inf
            results = []
            for rec_idx in top_indices(candidate_scores, limit):
                if not np.isfinite(candidate_scores[rec_idx]):
                    continue
                row = self._safe_row(int(rec_idx))
                row["score"] = float(clamp(candidate_scores[rec_idx]))
                row["algorithm"] = "hybrid"
                results.append(row)
            return results
        except Exception as exc:
            print(f"Error in hybrid: {exc}")
            return []

    def recommend_by_preference(
        self,
        preferences: str,
        limit: int = 10,
        context: Optional[dict[str, Any]] = None,
    ) -> List[Dict]:
        result = self.recommend_from_user_input(
            preferences=preferences,
            limit=limit,
            context=context,
            allow_ai_fallback=False,
        )
        return result["recommendations"]

    def recommend_from_user_input(
        self,
        preferences: str,
        limit: int = 10,
        context: Optional[dict[str, Any]] = None,
        allow_ai_fallback: bool = True,
    ) -> dict[str, Any]:
        profile = self._build_preference_profile(preferences, context=context)
        result = self._recommend_with_profile(profile, limit)
        result["requested_limit"] = limit

        should_try_ai = (
            allow_ai_fallback
            and settings.ai_fallback_enabled
            and self._can_use_ai_fallback()
            and (not result["recommendations"] or result["confidence"] < settings.ai_fallback_confidence_threshold)
        )
        if should_try_ai:
            ai_result = self._run_ai_fallback(profile, context=context)
            if ai_result is not None:
                merged_profile = self._merge_profiles(profile, ai_result["profile"], source=ai_result["provider"])
                retry = self._recommend_with_profile(merged_profile, limit)
                if self._prefer_fallback_result(result, retry):
                    retry["ai_fallback_used"] = True
                    retry["fallback_provider"] = ai_result["provider"]
                    retry["profile_source"] = merged_profile.source
                    retry["explanation"] = self._build_explanation(merged_profile, retry["recommendations"], ai_provider=ai_result["provider"])
                    return retry

        if not result["recommendations"]:
            fallback_recommendations = self._popular_fallback(limit)
            result["recommendations"] = fallback_recommendations
            result["confidence"] = 0.0
            result["algorithm"] = "popular_fallback"
            result["explanation"] = (
                "No strong direct match was found, so the system returned high-quality popular perfumes from the local dataset."
            )

        return result

    def _recommend_with_profile(self, profile: PreferenceProfile, limit: int) -> dict[str, Any]:
        if self.data is None or len(self.data) == 0 or self.tfidf_vectorizer is None or self.tfidf_matrix is None:
            return {
                "recommendations": [],
                "confidence": 0.0,
                "algorithm": "unavailable",
                "explanation": "The recommendation model is not ready yet.",
                "profile_source": profile.source,
            }

        query_text = profile.query_text
        positive_terms = set(profile.all_positive_terms)
        negative_terms = set(profile.disliked_notes)
        raw_query_terms = {
            token for token in tokenize_text(profile.raw_text)
            if token not in TEXT_STOPWORDS
        }
        broad_note_query = (
            not profile.reference_perfumes
            and len(raw_query_terms) <= 8
            and any(term in (positive_terms | raw_query_terms) for term in ("oud", "woody", "amber", "vanilla", "fresh", "citrus", "floral", "rose", "sweet", "spicy"))
        )

        if not query_text.strip() and not positive_terms:
            recommendations = self._popular_fallback(limit)
            return {
                "recommendations": recommendations,
                "confidence": 0.0,
                "algorithm": "popular_fallback",
                "explanation": "No preference details were provided, so the system returned strong all-round local matches.",
                "profile_source": profile.source,
            }

        query_vector = self.tfidf_vectorizer.transform([query_text])
        tfidf_scores = linear_kernel(query_vector, self.tfidf_matrix).ravel().astype(np.float32)  # type: ignore

        latent_scores = np.zeros(len(self.data), dtype=np.float32)
        knn_scores: dict[int, float] = {}
        if self.svd_model is not None and self.svd_embeddings is not None and self.svd_row_norms is not None:
            try:
                query_latent = self.svd_model.transform(query_vector).astype(np.float32)[0]  # type: ignore
                query_norm = float(np.linalg.norm(query_latent)) + 1e-8
                latent_scores = (
                    (self.svd_embeddings @ query_latent)
                    / (self.svd_row_norms * query_norm + 1e-8)
                ).astype(np.float32)
            except Exception:
                latent_scores = np.zeros(len(self.data), dtype=np.float32)

        if self.knn_model is not None and self.knn_svd_reducer is not None:
            try:
                reduced_query = self.knn_svd_reducer.transform(query_vector)
                neighbor_count = min(max(limit * 4, 12), getattr(self.knn_model, "n_neighbors", max(limit * 4, 12)))
                distances, indices = self.knn_model.kneighbors(reduced_query, n_neighbors=neighbor_count)
                knn_scores = {int(idx): float(1.0 - dist) for dist, idx in zip(distances[0], indices[0])}
            except Exception:
                knn_scores = {}

        candidate_set: set[int] = set(top_indices(tfidf_scores, max(limit * 25, 180)).tolist())
        if latent_scores.size:
            candidate_set.update(top_indices(latent_scores, max(limit * 15, 120)).tolist())
        candidate_set.update(knn_scores.keys())
        for token in list(positive_terms)[:16]:
            candidate_set.update(self.keyword_to_indices.get(token, []))

        if not candidate_set:
            return {
                "recommendations": [],
                "confidence": 0.0,
                "algorithm": "local_multi_signal",
                "explanation": self._build_explanation(profile, []),
                "profile_source": profile.source,
            }

        scored_rows: list[tuple[int, float, list[str]]] = []
        positive_count = max(1, len(positive_terms))
        negative_count = max(1, len(negative_terms))

        # Ensure required data structures exist
        if not (self.dataset_tokens and self.accord_tokens and self.name_brand_tokens and self.dataset_gender is not None):
            return {
                "recommendations": [],
                "confidence": 0.0,
                "algorithm": "unavailable",
                "explanation": "Data structures not prepared.",
                "profile_source": profile.source,
            }

        for idx in candidate_set:
            all_tokens = self.dataset_tokens[idx]
            accord_tokens = self.accord_tokens[idx]
            name_tokens = self.name_brand_tokens[idx]
            row = self.data.iloc[idx]
            rating = float(row.get("rating", 0) or 0)
            rating_count = float(row.get("rating_count", 0) or 0)

            # For broad prompts like "party woody oud", avoid obscure rows that
            # win only because they contain the exact notes. These prompts need
            # trustworthy, recognizable picks, not low-sample catalogue noise.
            if broad_note_query and (rating < 3.7 or rating_count < 25):
                continue

            direct_overlap = len(positive_terms & all_tokens) / positive_count if positive_terms else 0.0
            accord_overlap = len(positive_terms & accord_tokens) / positive_count if positive_terms else 0.0
            name_overlap = len(positive_terms & name_tokens) / positive_count if positive_terms else 0.0
            negative_overlap = len(negative_terms & all_tokens) / negative_count if negative_terms else 0.0
            gender_adjustment = self._gender_adjustment(profile.gender, str(self.dataset_gender[idx]))
            budget_adjustment = self._budget_adjustment(profile, float(row.get("price", 0) or 0))

            final_score = (
                0.38 * float(tfidf_scores[idx])      # TF-IDF semantic match
                + 0.16 * float(latent_scores[idx])   # SVD latent similarity
                + 0.10 * knn_scores.get(idx, 0.0)    # KNN neighbour match
                + 0.16 * accord_overlap              # Direct accord overlap (↑ from 0.12)
                + 0.08 * direct_overlap              # Full-text overlap (↑ from 0.07)
                + 0.04 * name_overlap                # Brand/name match
            )
            if self.quality_scores.size:
                if broad_note_query:
                    final_score += 0.10 * float(self.quality_scores[idx])
                    final_score += 0.14 * float(self.popularity_scores[idx])
                    if rating_count < 100:
                        final_score -= 0.10
                    elif rating_count < 500:
                        final_score -= 0.05
                else:
                    final_score += 0.06 * float(self.quality_scores[idx])
                    final_score += 0.04 * float(self.popularity_scores[idx])
            final_score += gender_adjustment + budget_adjustment
            final_score -= 0.10 * negative_overlap
            if self.title_penalties.size:
                final_score -= 0.14 * float(self.title_penalties[idx])  # ↑ from 0.12 — harder penalty for samplers

            matched_notes = sorted((positive_terms & accord_tokens) | (positive_terms & name_tokens))
            final_score = clamp(final_score)
            if final_score > 0.0:
                scored_rows.append((idx, final_score, matched_notes[:6]))

        scored_rows.sort(key=lambda item: item[1], reverse=True)

        # ── APPLY STRICT FILTERING (NEW) ─────────────────────────────
        # Import the improved filtering logic
        try:
            from .ml_model_improvements import improve_recommendations
            
            # Apply strict filtering with opposite note penalties
            scored_rows = improve_recommendations(
                scored_rows,
                profile,
                self.data,
            )
        except Exception as exc:
            # If filtering fails, continue with original scores
            print(f"Warning: Strict filtering failed: {exc}")

        recommendations = []
        for idx, score, matched_notes in scored_rows[:limit]:
            row = self._safe_row(idx)
            row["match_score"] = float(score)
            row["score"] = float(score)
            row["algorithm"] = "local_multi_signal"
            if matched_notes:
                row["matched_notes"] = matched_notes
            recommendations.append(row)

        confidence = self._estimate_confidence(scored_rows)
        return {
            "recommendations": recommendations,
            "confidence": confidence,
            "algorithm": "local_multi_signal",
            "explanation": self._build_explanation(profile, recommendations),
            "profile_source": profile.source,
        }

    def _estimate_confidence(self, scored_rows: list[tuple[int, float, list[str]]]) -> float:
        if not scored_rows:
            return 0.0
        top_scores = [row[1] for row in scored_rows[:5]]
        top_score = top_scores[0]
        average_top = float(np.mean(top_scores))
        return float(clamp(0.65 * top_score + 0.35 * average_top))  # type: ignore

    def _build_preference_profile(
        self,
        preferences: str,
        context: Optional[dict[str, Any]] = None,
    ) -> PreferenceProfile:
        context = context or {}
        raw_text = (preferences or "").strip()
        raw_tokens = tokenize_text(raw_text)
        cleaned_terms = [token for token in raw_tokens if token not in TEXT_STOPWORDS]
        lowered = raw_text.lower()

        liked_notes = list(context.get("liked_notes") or [])
        liked_notes.extend(cleaned_terms)
        disliked_notes = list(context.get("disliked_notes") or [])
        disliked_notes.extend(self._extract_negative_terms(raw_tokens))
        reference_perfumes = list(context.get("reference_perfumes") or [])

        gender = normalize_gender(
            context.get("preferred_gender")
            or context.get("gender")
            or self._infer_gender(raw_text)
        )
        occasion = normalize_text(
            context.get("occasion")
            or self._infer_bucket(raw_tokens, OCCASION_HINTS, raw_text)
        )
        season = normalize_text(
            context.get("season")
            or self._infer_bucket(raw_tokens, SEASON_HINTS, raw_text)
        )
        mood = normalize_text(
            context.get("mood")
            or self._infer_bucket(raw_tokens, MOOD_HINTS, raw_text)
        )

        expanded_terms: list[str] = []

        # Expand note synonyms
        for token in cleaned_terms:
            expanded_terms.extend(NOTE_SYNONYMS.get(token, ()))

        # Expand occasion hints
        if occasion:
            expanded_terms.extend(OCCASION_HINTS.get(occasion, ()))

        # Expand season hints
        if season:
            expanded_terms.extend(SEASON_HINTS.get(season, ()))

        # Expand mood hints
        if mood:
            expanded_terms.extend(MOOD_HINTS.get(mood, ()))

        # ── Smart intent expansion ────────────────────────────────────
        # "long lasting" / "long-lasting" / "strong" → longevity notes
        if any(p in lowered for p in ("long lasting", "long-lasting", "longevity", "all day", "all-day")):
            expanded_terms.extend(("amber", "musk", "patchouli", "woody", "oud", "vetiver"))

        # "strong" / "powerful" / "bold" / "intense" → heavy base notes
        if any(p in lowered for p in ("strong", "powerful", "bold", "intense", "heavy", "projection", "sillage")):
            expanded_terms.extend(("oud", "amber", "spicy", "woody", "leather", "patchouli"))

        # "light" / "subtle" / "soft" / "delicate" → light top notes
        if any(p in lowered for p in ("light", "subtle", "soft", "delicate", "gentle", "airy")):
            expanded_terms.extend(("fresh", "citrus", "floral", "musk", "clean", "aquatic"))

        # "sweet" / "gourmand" → dessert notes
        if any(p in lowered for p in ("sweet", "gourmand", "dessert", "candy", "sugar")):
            expanded_terms.extend(("vanilla", "caramel", "sweet", "fruity", "gourmand"))

        # "romantic" / "sensual" / "seductive" → warm florals
        if any(p in lowered for p in ("romantic", "sensual", "seductive", "intimate", "sexy")):
            expanded_terms.extend(("rose", "vanilla", "amber", "musk", "jasmine"))

        # "fresh" / "clean" / "crisp" → citrus/aquatic
        if any(p in lowered for p in ("fresh", "clean", "crisp", "cool", "aquatic")):
            expanded_terms.extend(("citrus", "aquatic", "green", "fresh", "bergamot"))

        # "woody" / "earthy" / "nature" → wood notes
        if any(p in lowered for p in ("woody", "earthy", "nature", "forest", "wood")):
            expanded_terms.extend(("cedar", "sandalwood", "vetiver", "woody", "earthy"))

        # "premium" / "luxury" / "expensive" / "niche" → prestige notes
        if any(p in lowered for p in ("premium", "luxury", "expensive", "niche", "high end", "designer")):
            expanded_terms.extend(("oud", "iris", "amber", "leather", "rose"))

        # Budget signals
        budget_min = self._coerce_budget(context.get("budget_min"))
        budget_max = self._coerce_budget(context.get("budget_max"))

        # Inline budget extraction from text (e.g. "under 2000", "₹500")
        if budget_max is None:
            budget_match = re.search(
                r"(?:under|below|less than|max|within|upto|up to)?\s*"
                r"(?:rs\.?|inr|₹|\$)?\s*(\d[\d,]*)\s*(?:rs\.?|inr|₹|rupees?)?",
                lowered,
            )
            if budget_match:
                try:
                    raw_amount = int(budget_match.group(1).replace(",", ""))
                    # Treat as INR if > 500, convert to USD
                    budget_max = round(raw_amount / 84.0, 1) if raw_amount > 500 else float(raw_amount)
                except (ValueError, AttributeError):
                    pass

        return PreferenceProfile(
            raw_text=raw_text,
            gender="" if gender == "unisex" and "unisex" not in lowered else gender,
            occasion=occasion,
            season=season,
            mood=mood,
            liked_notes=dedupe_terms(liked_notes),
            disliked_notes=dedupe_terms(disliked_notes),
            reference_perfumes=dedupe_terms(reference_perfumes),
            budget_min=budget_min,
            budget_max=budget_max,
            expanded_terms=dedupe_terms(expanded_terms),
            source="local",
        )

    def _merge_profiles(
        self,
        base: PreferenceProfile,
        enrichment: dict[str, Any],
        source: str,
    ) -> PreferenceProfile:
        return PreferenceProfile(
            raw_text=base.raw_text,
            gender=normalize_gender(enrichment.get("gender") or base.gender),
            occasion=normalize_text(enrichment.get("occasion") or base.occasion),
            season=normalize_text(enrichment.get("season") or base.season),
            mood=normalize_text(enrichment.get("mood") or base.mood),
            liked_notes=dedupe_terms([*base.liked_notes, *(enrichment.get("liked_notes") or []), *(enrichment.get("keywords") or [])]),
            disliked_notes=dedupe_terms([*base.disliked_notes, *(enrichment.get("disliked_notes") or [])]),
            reference_perfumes=dedupe_terms([*base.reference_perfumes, *(enrichment.get("reference_perfumes") or [])]),
            budget_min=base.budget_min if base.budget_min is not None else self._coerce_budget(enrichment.get("budget_min")),
            budget_max=base.budget_max if base.budget_max is not None else self._coerce_budget(enrichment.get("budget_max")),
            expanded_terms=dedupe_terms([*base.expanded_terms, *(enrichment.get("expanded_terms") or [])]),
            source=f"local+{source}",
        )

    def _prefer_fallback_result(self, original: dict[str, Any], retry: dict[str, Any]) -> bool:
        if not retry["recommendations"]:
            return False
        if not original["recommendations"]:
            return True
        return retry["confidence"] > original["confidence"] + 0.04

    def _run_ai_fallback(
        self,
        profile: PreferenceProfile,
        context: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        try:
            from .ai_fallback import enrich_preference_profile

            return enrich_preference_profile(profile.raw_text, context=context or {})
        except Exception as exc:
            print(f"AI fallback skipped: {exc}")
            return None

    def _can_use_ai_fallback(self) -> bool:
        return bool(settings.google_api_key or settings.openai_api_key)

    def _build_explanation(
        self,
        profile: PreferenceProfile,
        recommendations: list[dict[str, Any]],
        ai_provider: Optional[str] = None,
    ) -> str:
        """
        Build a natural, human-readable explanation of why these results were returned.
        Format: "Since it's for a [occasion], I focused on [notes] that [reason]."
        """
        # ── Occasion-specific openers ─────────────────────────────────
        OCCASION_OPENERS: dict[str, str] = {
            "wedding":  "Since it's for a wedding, I focused on strong, long-lasting fragrances that make an impression.",
            "date":     "For a date, I leaned toward warm and memorable scents — not too overpowering.",
            "office":   "For office wear, I picked subtle and clean fragrances that won't distract.",
            "work":     "For work, I picked subtle and clean fragrances that won't distract.",
            "daily":    "For daily wear, I focused on light, effortless scents you can wear all day.",
            "party":    "For a party, I went with bold and vibrant fragrances that stand out.",
            "night":    "For a night out, I focused on deep, intense scents with good projection.",
            "gym":      "For the gym, I picked fresh and clean fragrances that stay light.",
            "outdoor":  "For outdoor wear, I chose fresh and earthy scents that feel natural.",
            "formal":   "For a formal occasion, I focused on sophisticated and elegant fragrances.",
            "casual":   "For casual wear, I picked easy, wearable scents for everyday use.",
        }

        # ── Gender context ────────────────────────────────────────────
        GENDER_PHRASES: dict[str, str] = {
            "men":   "suited for men",
            "women": "suited for women",
        }

        # ── Build the explanation ─────────────────────────────────────
        parts: list[str] = []

        # Occasion opener (most informative)
        if profile.occasion and profile.occasion in OCCASION_OPENERS:
            parts.append(OCCASION_OPENERS[profile.occasion])
        elif profile.occasion:
            parts.append(f"Matched for {profile.occasion} wear.")

        # Gender context
        if profile.gender and profile.gender in GENDER_PHRASES:
            parts.append(f"Results are {GENDER_PHRASES[profile.gender]}.")

        # Season context
        if profile.season:
            season_map = {
                "summer": "light and fresh for warm weather",
                "winter": "warm and cozy for cold weather",
                "spring": "floral and fresh for spring",
                "autumn": "woody and earthy for autumn",
            }
            desc = season_map.get(profile.season, f"suited for {profile.season}")
            parts.append(f"Picked scents that are {desc}.")

        # Note preferences
        if profile.liked_notes:
            top_notes = list(profile.liked_notes[:4])
            parts.append(f"Prioritised notes: {', '.join(top_notes)}.")

        # Top match overlap
        if recommendations and recommendations[0].get("matched_notes"):
            matched = recommendations[0]["matched_notes"][:3]
            parts.append(f"Top match shares: {', '.join(matched)}.")

        # AI provider note
        if ai_provider:
            parts.append(f"Enhanced with {ai_provider} AI.")

        # Fallback if nothing was built
        if not parts:
            parts.append("Matched using multi-signal local ranking across 73,000+ fragrances.")

        return " ".join(parts)

    def _popular_fallback(self, limit: int = 10) -> list[dict[str, Any]]:
        if self.data is None or len(self.data) == 0:
            return []
        if self.quality_scores.size != len(self.data):
            results = []
            for idx in range(min(limit, len(self.data))):
                row = self._safe_row(idx)
                row["match_score"] = 0.0
                row["score"] = 0.0
                row["algorithm"] = "popular_fallback"
                results.append(row)
            return results

        # Filter out low-quality and sampler/tester products
        NOISE_PATTERN = re.compile(
            r"\b(sample|sampler|tester|vial|decant|bundle|set|kit|lot|mini|travel size)\b",
            re.IGNORECASE,
        )
        valid_mask = np.ones(len(self.data), dtype=bool)
        for i, row in enumerate(self.data.itertuples()):
            name = str(getattr(row, "name", ""))
            rating = float(getattr(row, "rating", 0) or 0)
            # Exclude samplers, testers, low-rated
            if NOISE_PATTERN.search(name) or rating < 3.5:
                valid_mask[i] = False

        ranking = self.quality_scores + (0.35 * self.popularity_scores) - (0.25 * self.title_penalties)
        # Zero out invalid entries
        ranking = ranking * valid_mask.astype(np.float32)

        results = []
        for idx in top_indices(ranking, limit * 2):  # over-fetch then filter
            if not valid_mask[idx]:
                continue
            row = self._safe_row(int(idx))
            row["match_score"] = float(clamp(ranking[idx]))
            row["score"] = float(clamp(ranking[idx]))
            row["algorithm"] = "popular_fallback"
            results.append(row)
            if len(results) >= limit:
                break
        return results

    def _gender_adjustment(self, requested: str, candidate: str) -> float:
        """
        Weighted scoring adjustment for gender match.
        Exact match: +0.10  (was +0.05)
        Unisex candidate: +0.04  (was +0.02)
        Wrong gender: -0.12  (was -0.05)
        """
        if not requested:
            return 0.0
        if requested == "unisex":
            return 0.02 if candidate == "unisex" else 0.0
        if candidate == requested:
            return 0.10   # strong reward for exact gender match
        if candidate == "unisex":
            return 0.04   # mild reward — unisex works for anyone
        return -0.12      # clear penalty for wrong gender

    def _budget_adjustment(self, profile: PreferenceProfile, price: float) -> float:
        if price <= 0:
            return 0.0
        if profile.budget_min is not None and price < profile.budget_min:
            return -0.01
        if profile.budget_max is not None and price > profile.budget_max:
            return -0.04
        return 0.02 if profile.budget_min is not None or profile.budget_max is not None else 0.0

    def _extract_negative_terms(self, tokens: list[str]) -> list[str]:
        negatives: list[str] = []
        for idx, token in enumerate(tokens[:-1]):
            if token in NEGATION_TOKENS:
                negatives.extend(tokens[idx + 1: idx + 4])
        return negatives

    def _infer_gender(self, raw_text: str) -> str:
        lowered = raw_text.lower()
        # Explicit female signals — check phrases first (most specific)
        FEMALE_SIGNALS = (
            "for women", "for woman", "for her", "for wife", "for girlfriend",
            "for sister", "for mom", "for mother", "for bride", "for girl",
            "for ladies", "for lady", "for my wife", "for my girlfriend",
            "for my sister", "for my mom", "for my mother", "for my daughter",
            "female", "ladies", "feminine", "bridal", "bride",
        )
        if any(s in lowered for s in FEMALE_SIGNALS):
            return "women"
        # Explicit male signals
        MALE_SIGNALS = (
            "for men", "for man", "for him", "for husband", "for boyfriend",
            "for brother", "for dad", "for father", "for groom", "for boy",
            "for gents", "for gentleman", "for my husband", "for my boyfriend",
            "for my brother", "for my dad", "for my father", "for my son",
            "male", "mens", "masculine", "gents",
        )
        if any(s in lowered for s in MALE_SIGNALS):
            return "men"
        if "unisex" in lowered or "gender neutral" in lowered or "gender-neutral" in lowered:
            return "unisex"
        return ""

    def _infer_bucket(self, tokens: list[str], mapping: dict[str, Any], raw_text: str = "") -> str:
        # Direct token match first
        for token in tokens:
            if token in mapping:
                return token
        # Multi-word phrase matching on raw text (more reliable)
        text = raw_text.lower() if raw_text else " ".join(tokens)
        _PHRASE_MAP: dict[str, str] = {
            # Occasion phrases
            "date night": "date", "night out": "night", "going out": "party",
            "day out": "casual", "every day": "daily", "day to day": "daily",
            "everyday": "daily", "all day": "daily",
            "work place": "office", "work wear": "office", "job interview": "office",
            "at work": "office", "to work": "office",
            "special occasion": "formal", "black tie": "formal",
            "wedding ceremony": "wedding", "wedding day": "wedding",
            "bridal": "wedding", "reception": "wedding", "nikah": "wedding",
            "work out": "gym", "working out": "gym", "at the gym": "gym",
            # Season phrases
            "hot weather": "summer", "cold weather": "winter",
            "rainy season": "monsoon", "spring time": "spring",
            "in summer": "summer", "in winter": "winter",
            "for summer": "summer", "for winter": "winter",
        }
        for phrase, bucket in _PHRASE_MAP.items():
            if phrase in text and bucket in mapping:
                return bucket
        return ""
        return ""

    def _coerce_budget(self, value: Any) -> Optional[float]:
        if value in (None, "", False):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Data access helpers
    # ------------------------------------------------------------------

    def get_perfume_details(self, perfume_id: Union[int, str]) -> dict[str, Any]:
        if self.data is None or len(self.data) == 0:
            return {}
        idx = self._resolve_index(perfume_id)
        if idx is None:
            return {}
        row = self.data.iloc[idx]
        return {
            "id": row.get("id", ""),
            "name": str(row.get("name", "Unknown")),
            "brand": str(row.get("brand", "Unknown")),
            "gender": normalize_gender(row.get("gender", "unisex")),
            "description": str(row.get("description", "")),
            "accords": clean_accords(row.get("accords", "")),
            "rating": float(row.get("rating", 4.0) or 4.0),
            "price": float(row.get("price", 0) or 0),
            "url": str(row.get("url", "")),
            "image_url": str(row.get("image_url", "")),
            "source": str(row.get("source", "unknown")),
            "rating_count": int(row.get("rating_count", 0) or 0),
            "sold": int(row.get("sold", 0) or 0),
        }

    def search_perfumes(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if self.data is None or len(self.data) == 0:
            return []
        normalized_query = normalize_text(query)
        if not normalized_query:
            return []

        query_tokens = {token for token in tokenize_text(query) if token not in TEXT_STOPWORDS}
        contains_masks = []
        for column in ("name", "brand", "accords", "description"):
            if column in self.data.columns:
                contains_masks.append(
                    self.data[column].astype(str).str.lower().str.contains(normalized_query, na=False)
                )

        matched_indices: set[int] = set()
        if contains_masks:
            combined_mask = reduce(operator.or_, contains_masks)
            matched_indices.update(np.where(combined_mask.to_numpy())[0].tolist())

        if self.tfidf_vectorizer is not None and self.tfidf_matrix is not None:
            try:
                query_vector = self.tfidf_vectorizer.transform([normalized_query])
                tfidf_scores = linear_kernel(query_vector, self.tfidf_matrix).ravel()
                matched_indices.update(top_indices(tfidf_scores, max(limit * 5, 40)).tolist())
            except Exception:
                tfidf_scores = np.zeros(len(self.data), dtype=np.float32)
        else:
            tfidf_scores = np.zeros(len(self.data), dtype=np.float32)

        scored = []
        for idx in matched_indices:
            name = self.data.iloc[idx].get("name", "")
            brand = self.data.iloc[idx].get("brand", "")
            all_tokens = self.dataset_tokens[idx] if idx < len(self.dataset_tokens) else set()

            exact_boost = 0.12 if normalized_query == normalize_text(name) or normalized_query == normalize_text(brand) else 0.0
            prefix_boost = 0.06 if normalize_text(name).startswith(normalized_query) else 0.0
            overlap = len(query_tokens & all_tokens) / max(1, len(query_tokens)) if query_tokens else 0.0
            score = 0.50 * float(tfidf_scores[idx]) + 0.22 * overlap
            if self.quality_scores.size:
                score += 0.12 * float(self.quality_scores[idx])
                score += 0.08 * float(self.popularity_scores[idx])
                score -= 0.08 * float(self.title_penalties[idx])
            score += exact_boost + prefix_boost
            scored.append((idx, clamp(score)))

        scored.sort(key=lambda item: item[1], reverse=True)
        return [self._safe_row(idx) for idx, _ in scored[:limit]]

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Backwards-compatible alias used by older tests/scripts."""
        return self.search_perfumes(query, limit)

    def get_model_info(self) -> dict[str, Any]:
        return {
            "dataset_size": len(self.data) if self.data is not None else 0,
            "tfidf_ready": self.tfidf_vectorizer is not None,
            "kmeans_ready": self.kmeans_model is not None,
            "svd_ready": self.svd_model is not None,
            "knn_ready": self.knn_model is not None,
            "rf_ready": self.rf_scorer is not None,
            "runtime_ready": bool(len(self.dataset_tokens)),
            "models_trained": self.__class__._models_trained,
            "metadata": self.training_metadata,
        }


AUTOLOAD_RECOMMENDER = os.getenv("PERFUME_SKIP_AUTOLOAD", "0") != "1"
# Create the singleton immediately with autoload=False so the server starts
# instantly. The startup event in main.py triggers background loading.
recommender = AdvancedPerfumeRecommender(autoload=False)
