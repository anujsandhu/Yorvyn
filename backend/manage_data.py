#!/usr/bin/env python3
"""
Yorvyn Dataset Management CLI.

Automated ingestion, cleaning, multi-source merging, validation,
and indexing for fragrance and fashion datasets.

Usage:
  python manage_data.py status
  python manage_data.py merge [--sources FILE1,FILE2] [--output OUTPUT_FILE]
  python manage_data.py clean --input FILE [--output OUTPUT_FILE]
  python manage_data.py validate [--dataset FILE]
  python manage_data.py reindex [--dataset FILE]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pandas as pd
from app.pipeline.dataset_manager import DatasetManager
from app.pipeline.fragrance_cleaner import FragranceCleaner
from app.pipeline.index_builder import IndexBuilder


def print_banner():
    print("=" * 65)
    print("      🌸 YORVYN DATA INGESTION & PIPELINE MANAGER 🌸")
    print("=" * 65)


def cmd_status(args: argparse.Namespace) -> None:
    print_banner()
    data_dir = backend_dir.parent / "data"
    dm = DatasetManager(data_dir=data_dir)

    print("\n📂 Datasets Directory:", data_dir)
    print("─" * 65)

    files = list(data_dir.glob("*.csv")) + list(data_dir.glob("*.xlsx"))
    for f in sorted(files):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  • {f.name:<32} ({size_mb:.2f} MB)")

    print("\n🧠 Active Taxonomies:")
    frag_tax = dm.fragrance_taxonomy
    fash_tax = dm.fashion_taxonomy
    print(f"  • Fragrance Note Categories : {len(frag_tax.get('note_synonyms', {})):,} families")
    print(f"  • Fragrance Occasion Hints  : {len(frag_tax.get('occasion_hints', {})):,} occasions")
    print(f"  • Fragrance Season Hints    : {len(frag_tax.get('season_hints', {})):,} seasons")
    print(f"  • Fashion Style Aesthetics  : {len(fash_tax.get('style_aesthetics', {})):,} aesthetics")
    print(f"  • Fashion Color Rules       : {len(fash_tax.get('harmonious_pairs', [])):,} harmonious pairs")

    print("\n📊 Master Runtime Catalog:")
    df = dm.get_master_dataframe()
    print(f"  • Loaded Perfumes           : {len(df):,} items")
    if not df.empty and "brand" in df.columns:
        print(f"  • Unique Brands             : {df['brand'].nunique():,}")
    print("=" * 65 + "\n")


def cmd_clean(args: argparse.Namespace) -> None:
    print_banner()
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: Input file does not exist: {input_path}")
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path.parent / f"{input_path.stem}_cleaned.csv"

    print(f"\n🧹 Cleaning dataset: {input_path.name}")
    cleaner = FragranceCleaner()

    try:
        if input_path.suffix.lower() == ".csv":
            df = pd.read_csv(input_path, encoding="utf-8", on_bad_lines="skip")
        elif input_path.suffix.lower() in [".xls", ".xlsx"]:
            df = pd.read_excel(input_path)
        else:
            print(f"❌ Unsupported format: {input_path.suffix}")
            sys.exit(1)
    except UnicodeDecodeError:
        df = pd.read_csv(input_path, encoding="latin1", on_bad_lines="skip")

    cleaned_df, stats = cleaner.clean_dataframe(df, verbose=True)
    cleaned_df.to_csv(output_path, index=False)

    print("\n📊 Cleaning Summary:")
    print(f"  • Initial records  : {stats['initial_rows']:,}")
    print(f"  • Noise filtered   : {stats['removed_noise']:,}")
    print(f"  • Fakes filtered   : {stats['removed_fakes']:,}")
    print(f"  • Missing fields   : {stats['removed_missing_fields']:,}")
    print(f"  • Duplicates pruned: {stats['removed_duplicates']:,}")
    print(f"  • Final Clean rows : {stats['final_rows']:,}")
    print(f"\n💾 Cleaned dataset saved to: {output_path}\n")


def cmd_merge(args: argparse.Namespace) -> None:
    print_banner()
    data_dir = backend_dir.parent / "data"

    if args.sources:
        sources = [Path(s.strip()) for s in args.sources.split(",")]
    else:
        # Default high-quality sources
        sources = [
            data_dir / "final_perfume_data.csv",
            data_dir / "fra_perfumes.csv",
            data_dir / "ebay_mens_perfume.csv",
            data_dir / "ebay_womens_perfume.csv",
        ]

    output_path = Path(args.output) if args.output else data_dir / "master_perfume_catalog.csv"

    print("\n🔄 Merging & Harmonizing Datasets:")
    for s in sources:
        print(f"  → {s.name}")

    cleaner = FragranceCleaner()
    master_df = cleaner.merge_datasets(sources, output_path=output_path, verbose=True)

    print(f"\n✅ Merged Master Catalog Created: {len(master_df):,} verified perfumes.")
    print(f"💾 Location: {output_path}\n")


def cmd_validate(args: argparse.Namespace) -> None:
    print_banner()
    data_dir = backend_dir.parent / "data"
    dm = DatasetManager(data_dir=data_dir)
    target_path = Path(args.dataset) if args.dataset else data_dir / "master_perfume_catalog.csv"

    if not target_path.exists():
        # Fallback to final_perfume_data.csv
        target_path = data_dir / "final_perfume_data.csv"

    if not target_path.exists():
        print(f"❌ Target dataset not found: {target_path}")
        sys.exit(1)

    print(f"\n🔍 Running Diagnostics on: {target_path.name}")
    df = dm._read_csv_safe(target_path)

    cleaner = FragranceCleaner()
    report = cleaner.generate_health_report(df)

    print("─" * 65)
    print(f"  Status               : {report['status']}")
    print(f"  Quality Score        : {report['quality_score'] * 100:.1f}%")
    print(f"  Total Perfumes       : {report['total_records']:,}")
    print(f"  Unique Brands        : {report['unique_brands']:,}")
    print(f"  Accords Coverage     : {report['accords_coverage']}")
    print(f"  Notes Coverage       : {report['notes_coverage']}")
    print(f"  Images Coverage      : {report['images_coverage']}")
    print(f"  Descriptions Coverage: {report['descriptions_coverage']}")
    print(f"  Gender Distribution  : {report['gender_distribution']}")
    print("─" * 65 + "\n")


def cmd_reindex(args: argparse.Namespace) -> None:
    print_banner()
    data_dir = backend_dir.parent / "data"
    models_dir = backend_dir.parent / "models"
    dm = DatasetManager(data_dir=data_dir)
    target_path = Path(args.dataset) if args.dataset else data_dir / "master_perfume_catalog.csv"

    if not target_path.exists():
        target_path = data_dir / "final_perfume_data.csv"

    print(f"\n⚙️  Re-indexing ML vector representations from: {target_path.name}")
    df = dm._read_csv_safe(target_path)

    builder = IndexBuilder(output_dir=models_dir)
    builder.build_indexes(df, save_artifacts=True, verbose=True)
    print("\n✅ Index build complete. Recommender runtime is ready!\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Yorvyn Dataset Ingestion, Cleaning, and Indexing Pipeline"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status
    subparsers.add_parser("status", help="Show current datasets and taxonomies status")

    # Clean
    clean_parser = subparsers.add_parser("clean", help="Clean and standardize a single dataset")
    clean_parser.add_argument("--input", required=True, help="Input CSV/Excel file path")
    clean_parser.add_argument("--output", help="Output CSV file path")

    # Merge
    merge_parser = subparsers.add_parser("merge", help="Merge multiple datasets into master catalog")
    merge_parser.add_argument("--sources", help="Comma-separated file paths")
    merge_parser.add_argument("--output", help="Output master catalog CSV path")

    # Validate
    val_parser = subparsers.add_parser("validate", help="Run quality score and health diagnostic report")
    val_parser.add_argument("--dataset", help="Target dataset CSV path")

    # Reindex
    idx_parser = subparsers.add_parser("reindex", help="Rebuild TF-IDF vector and ML similarity indexes")
    idx_parser.add_argument("--dataset", help="Target dataset CSV path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "status": cmd_status,
        "clean": cmd_clean,
        "merge": cmd_merge,
        "validate": cmd_validate,
        "reindex": cmd_reindex,
    }

    cmd_fn = commands.get(args.command)
    if cmd_fn:
        cmd_fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
