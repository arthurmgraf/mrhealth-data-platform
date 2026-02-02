#!/usr/bin/env python3
"""
Case Ficticio - Teste -- Incremental Sales Data Generator
=========================================================

Generates orders for a specific 2-hour business window.
Reuses generation logic from generate_fake_sales.py (no duplication).

Usage:
    python scripts/generate_incremental_sales.py --window-start 12:00 --window-end 14:00
    python scripts/generate_incremental_sales.py --window-start 18:00 --window-end 20:00 --upload
    python scripts/generate_incremental_sales.py --window-start 10:00 --window-end 12:00 --date 2026-02-01 --seed 42

Author: Arthur Graf -- Case Ficticio - Teste Project
Date: February 2026
"""

import argparse
import sys
import os
import random
from datetime import datetime
from pathlib import Path

import pandas as pd
from faker import Faker

# Enable importing from the same directory (scripts/)
sys.path.insert(0, str(Path(__file__).parent))
from generate_fake_sales import (
    PRODUCT_CATALOG,
    generate_unit_list,
    generate_orders_for_unit_day,
)

# ============================================================================
# WINDOW VOLUME PATTERNS
# ============================================================================

WINDOW_VOLUMES = {
    (10, 12): (1, 2),   # Morning ramp-up (brunch)
    (12, 14): (3, 5),   # Lunch peak
    (14, 16): (1, 2),   # Afternoon lull
    (16, 18): (2, 3),   # Late afternoon
    (18, 20): (4, 6),   # Dinner peak
    (20, 22): (2, 3),   # Evening wind-down
}


def get_volume_for_window(start_hour: int, end_hour: int) -> tuple[int, int]:
    """Return (min_orders, max_orders) for a business window."""
    key = (start_hour, end_hour)
    if key not in WINDOW_VOLUMES:
        print(f"[WARN] Unknown window {start_hour}:00-{end_hour}:00, using default (1, 2)")
        return (1, 2)
    return WINDOW_VOLUMES[key]


def upload_to_gcs(local_dir: Path, bucket_name: str, gcs_prefix: str) -> int:
    """Upload generated CSVs to GCS. Returns file count."""
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    count = 0

    for csv_file in local_dir.rglob("*.csv"):
        relative = csv_file.relative_to(local_dir)
        blob_name = f"{gcs_prefix}/{relative}".replace("\\", "/")
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(csv_file))
        count += 1
        print(f"  [UPLOAD] gs://{bucket_name}/{blob_name}")

    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate incremental sales data for a specific business window",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Lunch peak (3-5 orders/unit)
  python scripts/generate_incremental_sales.py --window-start 12:00 --window-end 14:00

  # Dinner peak with GCS upload
  python scripts/generate_incremental_sales.py --window-start 18:00 --window-end 20:00 --upload

  # Specific date, reproducible output
  python scripts/generate_incremental_sales.py --window-start 10:00 --window-end 12:00 \\
    --date 2026-02-01 --seed 42
        """,
    )
    parser.add_argument("--window-start", required=True, help="Window start time (HH:MM)")
    parser.add_argument("--window-end", required=True, help="Window end time (HH:MM)")
    parser.add_argument("--date", default=None, help="Date (YYYY-MM-DD, default: today)")
    parser.add_argument("--units", type=int, default=50, help="Number of restaurant units (default: 50)")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory (default: output)")
    parser.add_argument("--upload", action="store_true", help="Upload generated files to GCS after generation")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Parse window hours
    start_hour = int(args.window_start.split(":")[0])
    end_hour = int(args.window_end.split(":")[0])
    window_tag = f"window_{start_hour:02d}{end_hour:02d}"

    # Parse date
    date = datetime.strptime(args.date, "%Y-%m-%d") if args.date else datetime.now()
    year, month, day = date.strftime("%Y"), date.strftime("%m"), date.strftime("%d")

    # Get volume pattern for this window
    min_orders, max_orders = get_volume_for_window(start_hour, end_hour)

    print("=" * 60)
    print("Case Ficticio - Teste -- Incremental Sales Generator")
    print("=" * 60)
    print(f"  Window:  {args.window_start} - {args.window_end}")
    print(f"  Date:    {date.strftime('%Y-%m-%d')}")
    print(f"  Units:   {args.units}")
    print(f"  Volume:  {min_orders}-{max_orders} orders/unit")
    if args.seed is not None:
        print(f"  Seed:    {args.seed}")

    # Seed RNG
    if args.seed is not None:
        random.seed(args.seed)
        Faker.seed(args.seed)
    fake = Faker("pt_BR")
    if args.seed is not None:
        fake.seed_instance(args.seed)

    # Generate units
    units = generate_unit_list(args.units)

    # Generate and write data
    output_dir = Path(args.output_dir)
    total_orders = 0
    total_items = 0

    print(f"\n[GENERATING] {len(units)} units...")

    for unit in units:
        unit_dir = (
            output_dir / "csv_sales" / year / month / day
            / f"unit_{unit['id']:03d}" / window_tag
        )
        unit_dir.mkdir(parents=True, exist_ok=True)

        orders, items = generate_orders_for_unit_day(
            fake=fake,
            unit_id=unit["id"],
            date=date,
            min_orders=min_orders,
            max_orders=max_orders,
        )

        pd.DataFrame(orders).to_csv(
            unit_dir / "pedido.csv", index=False, sep=";", encoding="utf-8"
        )
        pd.DataFrame(items).to_csv(
            unit_dir / "item_pedido.csv", index=False, sep=";", encoding="utf-8"
        )

        total_orders += len(orders)
        total_items += len(items)

    print(f"\n[COMPLETE] Generated {total_orders:,} orders, {total_items:,} items")
    print(f"  Output: {output_dir / 'csv_sales' / year / month / day}")

    # Upload to GCS if requested
    if args.upload:
        import yaml
        config_path = Path("config/project_config.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)
        bucket = config["storage"]["bucket"]

        print(f"\n[UPLOADING] to gs://{bucket}/raw/csv_sales/...")
        day_dir = output_dir / "csv_sales" / year / month / day
        uploaded = upload_to_gcs(day_dir, bucket, f"raw/csv_sales/{year}/{month}/{day}")
        print(f"\n[UPLOADED] {uploaded} files")
        print(f"  csv-processor Cloud Function will trigger automatically for each file")

    return 0


if __name__ == "__main__":
    sys.exit(main())
