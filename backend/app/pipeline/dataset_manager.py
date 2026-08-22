"""
Centralized Dataset & Taxonomy Manager.
Single source of truth for runtime fragrance catalogs, fashion knowledge, and dynamic updates.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import pandas as pd

logger = logging.getLogger("yorvyn.pipeline.dataset_manager")


class DatasetManager:
    """
    Manages loading, caching, and serving fragrance datasets and fashion taxonomies.
    """

    def __init__(self, data_dir: Optional[Union[str, Path]] = None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parents[3] / "data"
        self.taxonomy_dir = self.data_dir / "taxonomy"

        self._fragrance_df: Optional[pd.DataFrame] = None
        self._fragrance_taxonomy: Optional[Dict[str, Any]] = None
        self._fashion_taxonomy: Optional[Dict[str, Any]] = None

    @property
    def fragrance_taxonomy(self) -> Dict[str, Any]:
        if self._fragrance_taxonomy is None:
            self.load_fragrance_taxonomy()
        return self._fragrance_taxonomy or {}

    @property
    def fashion_taxonomy(self) -> Dict[str, Any]:
        if self._fashion_taxonomy is None:
            self.load_fashion_taxonomy()
        return self._fashion_taxonomy or {}

    def load_fragrance_taxonomy(self) -> Dict[str, Any]:
        path = self.taxonomy_dir / "fragrance_taxonomy.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._fragrance_taxonomy = json.load(f)
                    return self._fragrance_taxonomy
            except Exception as e:
                logger.error(f"Error loading fragrance taxonomy: {e}")
        self._fragrance_taxonomy = {}
        return self._fragrance_taxonomy

    def load_fashion_taxonomy(self) -> Dict[str, Any]:
        path = self.taxonomy_dir / "fashion_taxonomy.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._fashion_taxonomy = json.load(f)
                    return self._fashion_taxonomy
            except Exception as e:
                logger.error(f"Error loading fashion taxonomy: {e}")
        self._fashion_taxonomy = {}
        return self._fashion_taxonomy

    def _read_csv_safe(self, path: Path) -> pd.DataFrame:
        for encoding in ("utf-8", "latin-1", "iso-8859-1", "cp1252"):
            try:
                return pd.read_csv(path, encoding=encoding, low_memory=False)
            except Exception:
                continue
        raise RuntimeError(f"Could not read {path}")

    def get_master_dataframe(self) -> pd.DataFrame:
        """
        Load master catalog with fallback to existing datasets.
        """
        if self._fragrance_df is not None:
            return self._fragrance_df

        # Priority 1: Master catalog
        master_path = self.data_dir / "master_perfume_catalog.csv"
        if master_path.exists():
            try:
                self._fragrance_df = self._read_csv_safe(master_path)
                return self._fragrance_df
            except Exception as e:
                logger.warning(f"Could not load master catalog {master_path}: {e}")

        # Priority 2: Final perfume data
        final_path = self.data_dir / "final_perfume_data.csv"
        if final_path.exists():
            try:
                self._fragrance_df = self._read_csv_safe(final_path)
                return self._fragrance_df
            except Exception as e:
                logger.warning(f"Could not load {final_path}: {e}")

        # Priority 3: Combined perfume data
        combined_path = self.data_dir / "combined_perfume_data.csv"
        if combined_path.exists():
            try:
                self._fragrance_df = self._read_csv_safe(combined_path)
                return self._fragrance_df
            except Exception as e:
                logger.warning(f"Could not load {combined_path}: {e}")

        # Fallback: empty dataframe
        self._fragrance_df = pd.DataFrame(columns=["name", "brand", "accords", "notes", "description", "gender"])
        return self._fragrance_df

    def reload(self) -> None:
        """Clear cache and reload all datasets and taxonomies."""
        self._fragrance_df = None
        self._fragrance_taxonomy = None
        self._fashion_taxonomy = None
        self.load_fragrance_taxonomy()
        self.load_fashion_taxonomy()
        self.get_master_dataframe()


# Global singleton instance
dataset_manager = DatasetManager()
