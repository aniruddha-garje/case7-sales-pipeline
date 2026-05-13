# notebooks/eda.py
# Exploratory Data Analysis — discovers the 4 intentional DQ issues in the dataset.
# Run: python notebooks/eda.py
# All findings are printed to stdout for documentation.

import glob
import os
import re
import sys
from collections import defaultdict

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "datasets")
LATE_DIR = os.path.join(DATA_DIR, "late_arrivals")

EXPECTED_COLUMNS = [
    "order_id", "order_timestamp", "customer_id", "product_id",
    "product_name", "category", "qty", "unit_price", "discount_pct", "region"
]

CRITICAL_COLUMNS = ["order_id", "customer_id", "qty", "unit_price", "discount_pct"]


def extract_date(filename: str) -> str:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return match.group(1) if match else "unknown"


def section(title: str):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run_eda():
    # ------------------------------------------------------------------ #
    # 1. File Inventory
    # ------------------------------------------------------------------ #
    section("1. FILE INVENTORY")

    main_files = sorted(glob.glob(os.path.join(DATA_DIR, "sales_*.csv")))
    late_files = sorted(glob.glob(os.path.join(LATE_DIR, "sales_*.csv")))
    all_files = main_files + late_files

    print(f"Main folder:      {len(main_files)} files")
    print(f"Late arrivals:    {len(late_files)} files")
    print(f"Total:            {len(all_files)} files")

    # Build date coverage
    main_dates = {extract_date(f) for f in main_files}
    late_dates = {extract_date(f) for f in late_files}
    all_dates = main_dates | late_dates

    expected_dates = {
        f"2025-03-{str(d).zfill(2)}" for d in range(1, 32)
    }
    missing_dates = sorted(expected_dates - all_dates)
    late_only_dates = sorted(late_dates - main_dates)

    print(f"\nExpected dates (March 2025): 31")
    print(f"Dates with files:            {len(all_dates)}")
    print(f"Missing dates:               {missing_dates or 'none'}")
    print(f"Dates only in late_arrivals: {late_only_dates or 'none'}")

    if late_files:
        print("\nLate arrival files:")
        for f in late_files:
            print(f"  {os.path.basename(f)}")

    # ------------------------------------------------------------------ #
    # 2. Schema Check
    # ------------------------------------------------------------------ #
    section("2. SCHEMA CHECK (looking for schema drift)")

    schema_issues = []
    for f in all_files:
        df_head = pd.read_csv(f, nrows=0)
        cols = list(df_head.columns)
        if cols != EXPECTED_COLUMNS:
            schema_issues.append((os.path.basename(f), cols))

    if schema_issues:
        print(f"SCHEMA DRIFT detected in {len(schema_issues)} file(s):")
        for fname, cols in schema_issues:
            extra = set(cols) - set(EXPECTED_COLUMNS)
            missing = set(EXPECTED_COLUMNS) - set(cols)
            renamed = []
            print(f"\n  File: {fname}")
            print(f"    Actual columns:   {cols}")
            print(f"    Expected columns: {EXPECTED_COLUMNS}")
            if extra:
                print(f"    Extra columns:    {sorted(extra)}")
            if missing:
                print(f"    Missing columns:  {sorted(missing)}")
    else:
        print("No schema drift detected — all files match expected columns.")

    # ------------------------------------------------------------------ #
    # 3. Duplicate Check
    # ------------------------------------------------------------------ #
    section("3. DUPLICATE CHECK (order_id uniqueness)")

    all_dfs = []
    for f in all_files:
        df = pd.read_csv(f, low_memory=False)
        # Normalize columns for drift files (best effort: use position)
        if list(df.columns) != EXPECTED_COLUMNS and len(df.columns) == len(EXPECTED_COLUMNS):
            df.columns = EXPECTED_COLUMNS
        df["_source_file"] = os.path.basename(f)
        all_dfs.append(df)

    combined = pd.concat(all_dfs, ignore_index=True)
    total_rows = len(combined)
    print(f"Total rows across all files: {total_rows:,}")

    dup_counts = combined.groupby("order_id").size().reset_index(name="count")
    dupes = dup_counts[dup_counts["count"] > 1]

    if len(dupes) > 0:
        print(f"\nDUPLICATION detected: {len(dupes):,} order_id(s) appear more than once")
        print(f"Total duplicate rows (excess): {dupes['count'].sum() - len(dupes):,}")
        # Show which files contain the duplicate order_ids
        dup_ids = set(dupes["order_id"])
        dup_rows = combined[combined["order_id"].isin(dup_ids)]
        dup_by_file = dup_rows.groupby("_source_file").size()
        print("\nDuplicate order_ids found in:")
        for fname, cnt in dup_by_file.items():
            print(f"  {fname}: {cnt} rows involved")
    else:
        print("No duplicate order_ids found.")

    # ------------------------------------------------------------------ #
    # 4. Null Analysis
    # ------------------------------------------------------------------ #
    section("4. NULL ANALYSIS (looking for null spikes)")

    null_threshold = 0.02  # 2% threshold for flagging
    null_issues = []

    for f in all_files:
        df = pd.read_csv(f, low_memory=False)
        if list(df.columns) != EXPECTED_COLUMNS and len(df.columns) == len(EXPECTED_COLUMNS):
            df.columns = EXPECTED_COLUMNS
        null_pct = df.isnull().mean()
        high_nulls = null_pct[null_pct > null_threshold]
        if len(high_nulls) > 0:
            null_issues.append((os.path.basename(f), high_nulls.to_dict(), len(df)))

    if null_issues:
        print(f"NULL SPIKE detected in {len(null_issues)} file(s):")
        for fname, null_dict, nrows in null_issues:
            print(f"\n  File: {fname} ({nrows:,} rows)")
            for col, pct in null_dict.items():
                print(f"    {col}: {pct:.1%} null ({int(pct * nrows):,} rows)")
    else:
        print("No null spikes detected (all columns < 2% null in every file).")

    # ------------------------------------------------------------------ #
    # 5. Basic Stats
    # ------------------------------------------------------------------ #
    section("5. BASIC STATISTICS")

    # Row counts per day
    rows_per_file = {}
    for f in all_files:
        df = pd.read_csv(f, low_memory=False)
        rows_per_file[os.path.basename(f)] = len(df)

    print(f"Min rows/day: {min(rows_per_file.values()):,}  ({min(rows_per_file, key=rows_per_file.get)})")
    print(f"Max rows/day: {max(rows_per_file.values()):,}  ({max(rows_per_file, key=rows_per_file.get)})")
    print(f"Avg rows/day: {sum(rows_per_file.values()) / len(rows_per_file):,.0f}")

    # Revenue preview (only where numeric columns are clean)
    numeric_ok = combined.dropna(subset=["qty", "unit_price", "discount_pct"])
    numeric_ok = numeric_ok[
        pd.to_numeric(numeric_ok["qty"], errors="coerce").notna() &
        pd.to_numeric(numeric_ok["unit_price"], errors="coerce").notna() &
        pd.to_numeric(numeric_ok["discount_pct"], errors="coerce").notna()
    ].copy()
    numeric_ok["revenue"] = (
        pd.to_numeric(numeric_ok["qty"]) *
        pd.to_numeric(numeric_ok["unit_price"]) *
        (1 - pd.to_numeric(numeric_ok["discount_pct"]))
    )

    print(f"\nRevenue stats (on {len(numeric_ok):,} rows with complete numeric fields):")
    print(f"  Min:   {numeric_ok['revenue'].min():,.2f}")
    print(f"  Max:   {numeric_ok['revenue'].max():,.2f}")
    print(f"  Total: {numeric_ok['revenue'].sum():,.2f}")

    # Unique values
    print(f"\nUnique products:   {combined['product_id'].nunique()}")
    print(f"Unique categories: {combined['category'].nunique()}")
    print(f"Unique regions:    {combined['region'].nunique()}")
    print(f"Unique customers:  {combined['customer_id'].nunique()}")

    section("EDA COMPLETE — Review findings above before building pipeline")


if __name__ == "__main__":
    run_eda()
