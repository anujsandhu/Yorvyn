"""
Schema validation and column auto-mapping for perfume and fashion datasets.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd


@dataclass
class PerfumeRecord:
    name: str
    brand: str
    accords: str = ""
    notes: str = ""
    description: str = ""
    gender: str = "unisex"
    rating: float = 0.0
    rating_count: int = 0
    price: float = 0.0
    image_url: str = ""
    url: str = ""
    raw_accords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SchemaValidator:
    """
    Intelligent column auto-detection and validation across heterogenous datasets.
    """

    # Field aliases mapping common dataset naming conventions to standard schema
    COLUMN_ALIASES: Dict[str, List[str]] = {
        "name": ["name", "title", "perfume", "fragrance_name", "product_name", "item_title", "perfume_name"],
        "brand": ["brand", "house", "designer", "brand_name", "company", "manufacturer"],
        "accords": ["accords", "main accords", "main_accords", "accord", "scent_profile", "accords_list"],
        "notes": ["notes", "fragrance_notes", "scent_notes", "pyramid", "top_notes", "ingredients"],
        "description": ["description", "desc", "about", "details", "fragrance_description", "summary"],
        "gender": ["gender", "for", "target_gender", "department", "category_gender", "sex"],
        "rating": ["rating", "rating value", "rating_value", "score", "review_score", "stars", "rating_val"],
        "rating_count": ["rating count", "rating_count", "votes", "num_reviews", "review_count", "reviews"],
        "price": ["price", "price_usd", "cost", "msrp", "retail_price"],
        "image_url": ["image url", "image_url", "image", "img", "thumbnail", "photo_url", "picture"],
        "url": ["url", "link", "product_url", "item_url", "fragrantica_url"]
    }

    @classmethod
    def map_columns(cls, df: pd.DataFrame) -> Dict[str, str]:
        """
        Detect and map raw DataFrame column names to standard schema keys.
        """
        mapping: Dict[str, str] = {}
        normalized_cols = {cls._clean_col_name(c): c for c in df.columns}

        for standard_key, aliases in cls.COLUMN_ALIASES.items():
            for alias in aliases:
                cleaned_alias = cls._clean_col_name(alias)
                if cleaned_alias in normalized_cols:
                    mapping[normalized_cols[cleaned_alias]] = standard_key
                    break

        return mapping

    @staticmethod
    def _clean_col_name(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", str(name).lower().strip())

    @classmethod
    def standardize_dataframe(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardize raw DataFrame into the canonical Yorvyn perfume schema.
        """
        if df is None or df.empty:
            return pd.DataFrame(columns=[
                "name", "brand", "accords", "notes", "description",
                "gender", "rating", "rating_count", "price", "image_url", "url"
            ])

        col_mapping = cls.map_columns(df)
        renamed_df = df.rename(columns=col_mapping).copy()

        # Ensure all canonical columns exist
        canonical_cols = [
            "name", "brand", "accords", "notes", "description",
            "gender", "rating", "rating_count", "price", "image_url", "url"
        ]
        for col in canonical_cols:
            if col not in renamed_df.columns:
                renamed_df[col] = ""

        # Keep only canonical columns (drop unmapped noise columns)
        return renamed_df[canonical_cols].copy()

    @classmethod
    def validate_schema(cls, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Check if DataFrame has necessary fields and minimal completeness.
        """
        errors = []
        if df is None or df.empty:
            return False, ["Dataset is completely empty."]

        for required in ["name", "brand"]:
            if required not in df.columns:
                errors.append(f"Missing mandatory column: '{required}'")

        if errors:
            return False, errors

        non_empty_names = df["name"].dropna().astype(str).str.strip().str.len() > 0
        if non_empty_names.sum() == 0:
            errors.append("Dataset has 0 rows with valid product names.")

        return len(errors) == 0, errors
