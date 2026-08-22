"""
Comprehensive Data Cleaner for Fragrance Datasets.
Deduplicates, sanitizes, normalizes, and enriches perfume records from multiple sources.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from .schema_validator import SchemaValidator

logger = logging.getLogger("yorvyn.pipeline.cleaner")


class FragranceCleaner:
    """
    Cleans raw fragrance data files, performs multi-source reconciliation,
    and produces high-quality master datasets.
    """

    def __init__(self, taxonomy_path: Optional[Union[str, Path]] = None):
        self.taxonomy_path = Path(taxonomy_path) if taxonomy_path else Path(__file__).resolve().parents[3] / "data" / "taxonomy" / "fragrance_taxonomy.json"
        self.taxonomy = self._load_taxonomy()

        self.noise_patterns = self.taxonomy.get("noise_title_tokens", [
            "sample", "tester", "vial", "decant", "mini", "set", "pack",
            "bundle", "lot", "gift set", "discovery", "variety", "empty bottle",
            "cleaning spray", "air freshener", "body spray", "travel size"
        ])
        self.fake_patterns = self.taxonomy.get("fake_patterns", [
            "inspired by", "type", "version", "similar to", "smells like",
            "dupe", "clone", "alternative", "impression", "replica"
        ])

    def _load_taxonomy(self) -> Dict[str, Any]:
        if self.taxonomy_path.exists():
            try:
                with open(self.taxonomy_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load taxonomy from {self.taxonomy_path}: {e}")
        return {}

    def clean_text(self, text: Any) -> str:
        """Sanitize unstructured text."""
        if text is None or (isinstance(text, float) and np.isnan(text)):
            return ""
        t = str(text).strip()
        t = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", t)  # strip control chars
        t = re.sub(r"\s+", " ", t)
        return t.strip()

    def parse_accords(self, raw: Any) -> str:
        """Normalize accords into a clean space-separated string."""
        if raw is None or (isinstance(raw, float) and np.isnan(raw)):
            return ""
        s = str(raw).strip()
        # Handle python string list format like "['citrus', 'woody']"
        s = re.sub(r"[\[\]'\"{}()]", " ", s)
        s = s.replace(",", " ").replace(";", " ")
        s = re.sub(r"\s+", " ", s).strip().lower()
        return s

    def normalize_gender(self, raw: Any, name_hint: str = "") -> str:
        """Normalize gender to 'men', 'women', or 'unisex'."""
        g = str(raw or "").lower().strip()
        combined = f"{g} {str(name_hint).lower()}".strip()

        if "women and men" in combined or "men and women" in combined or "unisex" in combined:
            return "unisex"
        if "for women" in combined or "women" in g or "female" in g or "pour femme" in combined or "woman" in combined:
            return "women"
        if "for men" in combined or "men" in g or "male" in g or "pour homme" in combined or "man" in combined:
            return "men"
        return "unisex"

    def clean_dataframe(
        self,
        df: pd.DataFrame,
        min_name_len: int = 2,
        min_brand_len: int = 2,
        min_rating: float = 1.0,
        verbose: bool = False
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Run the complete cleaning and sanitization pipeline on a DataFrame.
        """
        stats: Dict[str, Any] = {
            "initial_rows": len(df),
            "removed_noise": 0,
            "removed_fakes": 0,
            "removed_missing_fields": 0,
            "removed_low_ratings": 0,
            "removed_duplicates": 0,
            "final_rows": 0,
        }

        if df is None or df.empty:
            return pd.DataFrame(), stats

        # Standardize columns first
        clean_df = SchemaValidator.standardize_dataframe(df)

        # 1. Strip and clean string columns
        for col in ["name", "brand", "notes", "description", "image_url", "url"]:
            clean_df[col] = clean_df[col].apply(self.clean_text)

        clean_df["accords"] = clean_df["accords"].apply(self.parse_accords)

        # If accords is empty, fallback to notes or description keywords
        missing_accords = clean_df["accords"] == ""
        if missing_accords.any():
            clean_df.loc[missing_accords, "accords"] = clean_df.loc[missing_accords, "notes"].apply(self.parse_accords)

        # 2. Filter noise patterns in name / title
        noise_regex = r"\b(?:" + "|".join(re.escape(p) for p in self.noise_patterns) + r")\b"
        noise_mask = clean_df["name"].str.lower().str.contains(noise_regex, regex=True, na=False)
        stats["removed_noise"] = int(noise_mask.sum())
        clean_df = clean_df[~noise_mask]

        # 3. Filter fake / dupe patterns
        fake_regex = r"\b(?:" + "|".join(re.escape(p) for p in self.fake_patterns) + r")\b"
        fake_mask = clean_df["name"].str.lower().str.contains(fake_regex, regex=True, na=False)
        stats["removed_fakes"] = int(fake_mask.sum())
        clean_df = clean_df[~fake_mask]

        # 4. Mandatory minimum length checks
        valid_len = (clean_df["name"].str.len() >= min_name_len) & (clean_df["brand"].str.len() >= min_brand_len)
        stats["removed_missing_fields"] = int((~valid_len).sum())
        clean_df = clean_df[valid_len]

        # 5. Clean ratings and prices
        clean_df["rating"] = pd.to_numeric(clean_df["rating"], errors="coerce").fillna(0.0)
        clean_df["rating_count"] = pd.to_numeric(clean_df["rating_count"], errors="coerce").fillna(0).astype(int)
        clean_df["price"] = pd.to_numeric(clean_df["price"], errors="coerce").fillna(0.0)

        # Drop entries with non-zero invalid ratings below threshold
        low_rating_mask = (clean_df["rating"] > 0) & (clean_df["rating"] < min_rating)
        stats["removed_low_ratings"] = int(low_rating_mask.sum())
        clean_df = clean_df[~low_rating_mask]

        # 6. Normalize gender
        clean_df["gender"] = [
            self.normalize_gender(g, n) for g, n in zip(clean_df["gender"], clean_df["name"])
        ]

        # 7. Deduplicate on normalized name & brand
        clean_df["_dedupe_key"] = (
            clean_df["name"].str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
            + "_"
            + clean_df["brand"].str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
        )
        before_dedupe = len(clean_df)
        clean_df = clean_df.drop_duplicates(subset=["_dedupe_key"], keep="first")
        stats["removed_duplicates"] = before_dedupe - len(clean_df)
        clean_df = clean_df.drop(columns=["_dedupe_key"])

        # 8. Reset index and add unique ID
        clean_df = clean_df.reset_index(drop=True)
        clean_df.insert(0, "id", range(len(clean_df)))
        stats["final_rows"] = len(clean_df)

        if verbose:
            logger.info(f"Cleaned {stats['initial_rows']} -> {stats['final_rows']} rows.")

        return clean_df, stats

    def merge_datasets(
        self,
        filepaths: List[Union[str, Path]],
        output_path: Optional[Union[str, Path]] = None,
        verbose: bool = True
    ) -> pd.DataFrame:
        """
        Load, merge, and clean multiple perfume datasets into a single master catalog.
        """
        dfs = []
        for path_item in filepaths:
            p = Path(path_item)
            if not p.exists():
                logger.warning(f"File not found: {p}")
                continue

            try:
                if p.suffix.lower() == ".csv":
                    # Try utf-8 then latin1
                    try:
                        raw_df = pd.read_csv(p, encoding="utf-8")
                    except UnicodeDecodeError:
                        raw_df = pd.read_csv(p, encoding="latin1")
                elif p.suffix.lower() in [".xls", ".xlsx"]:
                    raw_df = pd.read_excel(p)
                elif p.suffix.lower() == ".json":
                    raw_df = pd.read_json(p)
                else:
                    logger.warning(f"Unsupported file format: {p}")
                    continue

                cleaned, stats = self.clean_dataframe(raw_df, verbose=verbose)
                if not cleaned.empty:
                    dfs.append(cleaned)
                    if verbose:
                        print(f"   ✓ Ingested {p.name}: {len(cleaned):,} clean records")
            except Exception as e:
                logger.error(f"Failed to read {p}: {e}")

        if not dfs:
            return pd.DataFrame()

        combined = pd.concat(dfs, ignore_index=True)
        # Final master deduplication
        master_df, _ = self.clean_dataframe(combined, verbose=verbose)

        if output_path:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            master_df.to_csv(out_p, index=False)
            if verbose:
                print(f"\n   💾 Master catalog exported to {out_p} ({len(master_df):,} entries)")

        return master_df

    def generate_health_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate comprehensive validation and quality diagnostics for a dataset.
        """
        if df is None or df.empty:
            return {"status": "EMPTY", "quality_score": 0.0, "error": "No records in dataset"}

        # Standardize dataframe so canonical columns are guaranteed to exist
        df = SchemaValidator.standardize_dataframe(df)

        total = len(df)
        has_accords = (df["accords"].astype(str).str.strip().str.len() > 0).sum()
        has_notes = (df["notes"].astype(str).str.strip().str.len() > 0).sum()
        has_desc = (df["description"].astype(str).str.strip().str.len() > 0).sum()
        has_img = (df["image_url"].astype(str).str.strip().str.len() > 0).sum()

        unique_brands = df["brand"].nunique()
        unique_names = df["name"].nunique()

        # Quality scoring weights:
        # Completeness (40%), Metadata richness (30%), Brand diversity (15%), Accords coverage (15%)
        completeness = (has_accords + has_notes) / (2 * total) if total > 0 else 0
        richness = (has_desc + has_img) / (2 * total) if total > 0 else 0
        diversity = min(1.0, unique_brands / 150)
        accords_cov = has_accords / total if total > 0 else 0

        quality_score = float(np.round((completeness * 0.4) + (richness * 0.3) + (diversity * 0.15) + (accords_cov * 0.15), 3))

        gender_counts = df["gender"].value_counts().to_dict()

        return {
            "status": "HEALTHY" if quality_score >= 0.6 else "NEEDS_ENRICHMENT",
            "quality_score": quality_score,
            "total_records": int(total),
            "unique_brands": int(unique_brands),
            "unique_perfumes": int(unique_names),
            "accords_coverage": f"{(has_accords / total * 100):.1f}%",
            "notes_coverage": f"{(has_notes / total * 100):.1f}%",
            "descriptions_coverage": f"{(has_desc / total * 100):.1f}%",
            "images_coverage": f"{(has_img / total * 100):.1f}%",
            "gender_distribution": gender_counts,
        }
