"""
Dataset Cleaner — Pre-process perfume dataset to remove noise and improve quality.

This module cleans the dataset ONCE before loading to ensure:
- No non-perfume items (cleaning sprays, air fresheners)
- No fake/irrelevant products
- No broken entries
- No duplicates
- Only valid perfumes with critical fields

Run this during model training to improve recommendation quality.
"""
from __future__ import annotations
import re
import pandas as pd
import numpy as np
from typing import Optional


# ── Noise Patterns ────────────────────────────────────────────────────

NOISE_PATTERNS = [
    "sample", "tester", "vial", "decant", "mini", "set", 
    "pack", "bundle", "lot", "gift set", "discovery", 
    "variety", "empty bottle", "cleaning spray", "air freshener",
    "room spray", "car freshener", "deodorizer", "sanitizer",
    "body spray", "body mist", "travel size", "sampler set",
    "tester set", "gift pack", "variety pack", "discovery set",
]

# Patterns that indicate fake/irrelevant products
FAKE_PATTERNS = [
    "inspired by", "type", "version", "similar to", "smells like",
    "dupe", "clone", "alternative", "impression", "replica",
]

# Minimum quality thresholds
MIN_RATING = 2.0
MIN_NAME_LENGTH = 3
MIN_BRAND_LENGTH = 2


def clean_dataset(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Clean dataset ONCE before loading.
    
    Removes:
    - Non-perfume items
    - Fake/irrelevant products
    - Broken entries
    - Duplicates
    - Low-quality entries
    
    Args:
        df: Raw perfume DataFrame
        verbose: Print cleaning statistics
        
    Returns:
        Cleaned DataFrame
    """
    if df is None or len(df) == 0:
        return df
    
    original_count = len(df)
    
    # ── Step 1: Remove noise patterns ─────────────────────────────────
    noise_pattern = '|'.join(NOISE_PATTERNS)
    noise_mask = df['name'].str.lower().str.contains(noise_pattern, na=False, regex=True)
    df = df[~noise_mask]
    
    if verbose:
        removed = original_count - len(df)
        print(f"   ✓ Removed {removed:,} noise entries (samples, testers, sets)")
    
    # ── Step 2: Remove fake/inspired products ─────────────────────────
    fake_pattern = '|'.join(FAKE_PATTERNS)
    fake_mask = df['name'].str.lower().str.contains(fake_pattern, na=False, regex=True)
    df = df[~fake_mask]
    
    if verbose:
        removed = original_count - len(df)
        print(f"   ✓ Removed {removed - (original_count - len(df)):,} fake/inspired products")
    
    # ── Step 3: Remove entries with missing critical fields ───────────
    before_missing = len(df)
    df = df.dropna(subset=['name', 'brand'])
    df = df[df['name'].str.len() >= MIN_NAME_LENGTH]
    df = df[df['brand'].str.len() >= MIN_BRAND_LENGTH]
    
    if verbose:
        removed = before_missing - len(df)
        print(f"   ✓ Removed {removed:,} entries with missing/invalid fields")
    
    # ── Step 4: Remove very low ratings ───────────────────────────────
    before_rating = len(df)
    if 'rating' in df.columns:
        df['rating'] = pd.to_numeric(df['rating'], errors='coerce')
        df = df[df['rating'] >= MIN_RATING]
    
    if verbose:
        removed = before_rating - len(df)
        print(f"   ✓ Removed {removed:,} low-rated entries (< {MIN_RATING})")
    
    # ── Step 5: Remove entries with no accords/notes ──────────────────
    before_accords = len(df)
    if 'accords' in df.columns:
        df = df[df['accords'].notna()]
        df = df[df['accords'].astype(str).str.len() > 0]
    
    if verbose:
        removed = before_accords - len(df)
        print(f"   ✓ Removed {removed:,} entries with no accords/notes")
    
    # ── Step 6: Remove duplicates ─────────────────────────────────────
    before_dupes = len(df)
    df = df.drop_duplicates(subset=['name', 'brand'], keep='first')
    
    if verbose:
        removed = before_dupes - len(df)
        print(f"   ✓ Removed {removed:,} duplicate entries")
    
    # ── Step 7: Clean and normalize fields ────────────────────────────
    df['name'] = df['name'].str.strip()
    df['brand'] = df['brand'].str.strip()
    
    # Normalize gender
    if 'gender' in df.columns:
        df['gender'] = df['gender'].fillna('unisex')
        df['gender'] = df['gender'].str.lower()
        df['gender'] = df['gender'].replace({
            'male': 'men',
            'female': 'women',
            'both': 'unisex',
            'neutral': 'unisex',
        })
    
    # Ensure numeric fields are valid
    if 'price' in df.columns:
        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0)
    
    if 'rating_count' in df.columns:
        df['rating_count'] = pd.to_numeric(df['rating_count'], errors='coerce').fillna(0)
    
    if 'sold' in df.columns:
        df['sold'] = pd.to_numeric(df['sold'], errors='coerce').fillna(0)
    
    # ── Step 8: Reset index ───────────────────────────────────────────
    df = df.reset_index(drop=True)
    df['id'] = range(len(df))
    
    # ── Final statistics ──────────────────────────────────────────────
    final_count = len(df)
    total_removed = original_count - final_count
    retention_rate = (final_count / original_count * 100) if original_count > 0 else 0
    
    if verbose:
        print(f"\n   📊 Cleaning Summary:")
        print(f"      Original: {original_count:,} entries")
        print(f"      Cleaned:  {final_count:,} entries")
        print(f"      Removed:  {total_removed:,} entries ({100 - retention_rate:.1f}%)")
        print(f"      Retained: {retention_rate:.1f}%\n")
    
    return df


def validate_dataset(df: pd.DataFrame) -> dict:
    """
    Validate cleaned dataset quality.
    
    Returns:
        Dictionary with validation metrics
    """
    if df is None or len(df) == 0:
        return {
            "valid": False,
            "error": "Empty dataset",
        }
    
    # Check required columns
    required_columns = ['name', 'brand', 'accords']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        return {
            "valid": False,
            "error": f"Missing required columns: {missing_columns}",
        }
    
    # Calculate quality metrics
    metrics = {
        "valid": True,
        "total_entries": len(df),
        "unique_brands": df['brand'].nunique(),
        "unique_perfumes": df['name'].nunique(),
        "avg_rating": df['rating'].mean() if 'rating' in df.columns else None,
        "entries_with_images": (df['image_url'].notna() & (df['image_url'] != '')).sum() if 'image_url' in df.columns else 0,
        "entries_with_descriptions": (df['description'].notna() & (df['description'] != '')).sum() if 'description' in df.columns else 0,
        "gender_distribution": df['gender'].value_counts().to_dict() if 'gender' in df.columns else {},
    }
    
    return metrics


def get_quality_score(df: pd.DataFrame) -> float:
    """
    Calculate overall dataset quality score (0.0 - 1.0).
    
    Args:
        df: Cleaned DataFrame
        
    Returns:
        Quality score
    """
    if df is None or len(df) == 0:
        return 0.0
    
    score = 0.0
    
    # Check completeness (40%)
    required_fields = ['name', 'brand', 'accords']
    completeness = sum(df[col].notna().sum() / len(df) for col in required_fields if col in df.columns) / len(required_fields)
    score += completeness * 0.4
    
    # Check rating quality (30%)
    if 'rating' in df.columns:
        avg_rating = df['rating'].mean()
        rating_quality = min(1.0, avg_rating / 4.5)  # Target: 4.5+
        score += rating_quality * 0.3
    else:
        score += 0.15  # Partial credit if no ratings
    
    # Check metadata richness (20%)
    has_images = (df['image_url'].notna() & (df['image_url'] != '')).sum() / len(df) if 'image_url' in df.columns else 0
    has_descriptions = (df['description'].notna() & (df['description'] != '')).sum() / len(df) if 'description' in df.columns else 0
    metadata_quality = (has_images + has_descriptions) / 2
    score += metadata_quality * 0.2
    
    # Check diversity (10%)
    unique_brands = df['brand'].nunique()
    unique_perfumes = df['name'].nunique()
    diversity = min(1.0, (unique_brands / 100) * 0.5 + (unique_perfumes / len(df)) * 0.5)
    score += diversity * 0.1
    
    return min(1.0, max(0.0, score))


# ── Example Usage ─────────────────────────────────────────────────────

if __name__ == "__main__":
    # Example: Clean a dataset
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python dataset_cleaner.py <input_csv> [output_csv]")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.replace('.csv', '_cleaned.csv')
    
    print(f"\n🧹 Cleaning dataset: {input_path}\n")
    
    # Load dataset
    df = pd.read_csv(input_path)
    print(f"   Loaded {len(df):,} entries")
    
    # Clean dataset
    cleaned_df = clean_dataset(df, verbose=True)
    
    # Validate
    validation = validate_dataset(cleaned_df)
    if validation['valid']:
        print(f"   ✅ Dataset validation passed")
        print(f"      Unique brands: {validation['unique_brands']:,}")
        print(f"      Unique perfumes: {validation['unique_perfumes']:,}")
        if validation['avg_rating']:
            print(f"      Average rating: {validation['avg_rating']:.2f}")
    
    # Quality score
    quality = get_quality_score(cleaned_df)
    print(f"\n   📈 Dataset Quality Score: {quality:.1%}\n")
    
    # Save cleaned dataset
    cleaned_df.to_csv(output_path, index=False)
    print(f"   💾 Saved cleaned dataset to: {output_path}\n")
