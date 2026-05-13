# pipeline/ingest.py
# Scans datasets/ and datasets/late_arrivals/, loads all CSVs into DuckDB raw_orders table.
# Tags each row with _source_file, _load_timestamp, _file_date for lineage.

import glob
import os
import re
from datetime import datetime

import duckdb
import pandas as pd

# Expected columns after schema normalization
EXPECTED_COLUMNS = [
    "order_id", "order_timestamp", "customer_id", "product_id",
    "product_name", "category", "qty", "unit_price", "discount_pct", "region"
]


def extract_file_date(filename: str) -> str:
    """Extract the date string from a filename like sales_2025-03-01.csv."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return match.group(1) if match else None


def normalize_columns(df: pd.DataFrame, source_file: str) -> pd.DataFrame:
    """
    Normalize column names to the expected schema.
    Handles schema drift by renaming known aliases and adding missing columns as NULL.
    """
    # TODO: implement column normalization after EDA reveals actual drift
    return df


def ingest_all(db_path: str, data_dir: str) -> dict:
    """
    Load all CSV files from data_dir and data_dir/late_arrivals into DuckDB raw_orders.

    Args:
        db_path: Path to the DuckDB file (created if not exists).
        data_dir: Directory containing sales_*.csv files.

    Returns:
        dict with keys: total_rows, files_loaded, files_skipped
    """
    # TODO: implement in Phase 2
    raise NotImplementedError("Implement in Phase 2")


if __name__ == "__main__":
    # Quick smoke test
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = ingest_all(
        db_path=os.path.join(ROOT, "output", "sales.duckdb"),
        data_dir=os.path.join(ROOT, "datasets")
    )
    print(result)
