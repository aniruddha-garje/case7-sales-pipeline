# pipeline/ingest.py
# Scans datasets/ and datasets/late_arrivals/, loads all CSVs into DuckDB raw_orders.
# Tags each row with _source_file, _load_timestamp, _file_date for lineage.
#
# Schema drift handling (discovered in EDA):
#   - sales_2025-03-22.csv: renames 'item_name' → 'product_name', drops 'channel'

import glob
import os
import re
from datetime import datetime

import duckdb
import pandas as pd

# Canonical column order for raw_orders
EXPECTED_COLUMNS = [
    "order_id", "order_timestamp", "customer_id", "product_id",
    "product_name", "category", "qty", "unit_price", "discount_pct", "region"
]

# Known column renames to handle schema drift (old_name → new_name)
COLUMN_RENAMES = {
    "item_name": "product_name",
}


def extract_file_date(filename: str) -> str:
    """Extract the date string from a filename like sales_2025-03-01.csv → '2025-03-01'."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return match.group(1) if match else None


def normalize_columns(df: pd.DataFrame, source_file: str) -> pd.DataFrame:
    """
    Normalize a DataFrame to EXPECTED_COLUMNS.

    Steps:
      1. Apply known renames (e.g. item_name → product_name)
      2. Drop any extra columns not in EXPECTED_COLUMNS
      3. Add any missing expected columns as NULL

    Returns the normalized DataFrame (always has exactly EXPECTED_COLUMNS).
    """
    # Step 1: rename known aliases
    df = df.rename(columns=COLUMN_RENAMES)

    # Step 2: identify extras and missing
    actual = set(df.columns)
    expected = set(EXPECTED_COLUMNS)
    extra = actual - expected
    missing = expected - actual

    if extra:
        print(f"  [INGEST] Schema drift in {source_file}: dropping extra columns {sorted(extra)}")
        df = df.drop(columns=list(extra))

    if missing:
        print(f"  [INGEST] Schema drift in {source_file}: adding missing columns as NULL {sorted(missing)}")
        for col in missing:
            df[col] = None

    # Step 3: enforce canonical column order
    df = df[EXPECTED_COLUMNS]
    return df


def load_sql(filename: str) -> str:
    """Load a SQL file from the sql/ directory relative to this file."""
    sql_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")
    with open(os.path.join(sql_dir, filename), "r") as f:
        return f.read()


def ingest_all(db_path: str, data_dir: str) -> dict:
    """
    Load all CSV files from data_dir and data_dir/late_arrivals/ into DuckDB raw_orders.

    - Idempotent: drops and recreates raw_orders on every call.
    - Tags each row with _source_file, _load_timestamp, _file_date for lineage.
    - Handles schema drift by normalizing columns before loading.

    Args:
        db_path: Path to the DuckDB file (created if not exists).
        data_dir: Directory containing sales_*.csv files.

    Returns:
        dict: {total_rows, files_loaded, files_skipped, skipped_files}
    """
    con = duckdb.connect(db_path)

    # Create the raw_orders table (idempotent DROP + CREATE)
    con.execute(load_sql("create_raw.sql"))
    print("[INGEST] Created raw_orders table (idempotent)")

    # Gather files from both main folder and late_arrivals/
    main_files = sorted(glob.glob(os.path.join(data_dir, "sales_*.csv")))
    late_files = sorted(glob.glob(os.path.join(data_dir, "late_arrivals", "sales_*.csv")))
    all_files = main_files + late_files

    print(f"[INGEST] Found {len(main_files)} files in main folder, "
          f"{len(late_files)} in late_arrivals/ — processing {len(all_files)} total")

    load_timestamp = datetime.now()
    total_rows = 0
    files_loaded = 0
    files_skipped = []

    for filepath in all_files:
        filename = os.path.basename(filepath)
        file_date = extract_file_date(filename)

        if file_date is None:
            print(f"  [INGEST] SKIP {filename} — could not extract date from filename")
            files_skipped.append(filename)
            continue

        try:
            df = pd.read_csv(filepath, low_memory=False)
        except Exception as e:
            print(f"  [INGEST] ERROR reading {filename}: {e}")
            files_skipped.append(filename)
            continue

        # Normalize to expected schema (handles drift)
        df = normalize_columns(df, filename)

        # Add lineage metadata columns
        df["_source_file"]     = filename
        df["_load_timestamp"]  = load_timestamp
        df["_file_date"]       = pd.to_datetime(file_date).date()

        # Append to raw_orders
        con.execute("INSERT INTO raw_orders SELECT * FROM df")

        row_count = len(df)
        total_rows += row_count
        files_loaded += 1
        print(f"  [INGEST] Loaded {row_count:,} rows from {filename} (date: {file_date})")

    print(f"[INGEST] Done — {total_rows:,} total rows from {files_loaded} files "
          f"({len(files_skipped)} skipped)")

    con.close()

    return {
        "total_rows":    total_rows,
        "files_loaded":  files_loaded,
        "files_skipped": len(files_skipped),
        "skipped_files": files_skipped,
    }


if __name__ == "__main__":
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = ingest_all(
        db_path=os.path.join(ROOT, "output", "sales.duckdb"),
        data_dir=os.path.join(ROOT, "datasets")
    )
    print(result)
