# pipeline/transform.py
# Transforms raw_orders → clean_orders → fact_orders + dimensions.
# Handles deduplication, null quarantine, revenue calculation, and dimension tables.
# All SQL is loaded from sql/*.sql files for readability.

import os
import duckdb


def load_sql(filename: str) -> str:
    """Load a SQL file from the sql/ directory."""
    sql_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")
    with open(os.path.join(sql_dir, filename), "r") as f:
        return f.read()


def transform_all(con: duckdb.DuckDBPyConnection) -> dict:
    """
    Run the full transformation chain:
      raw_orders → clean_orders (dedup) → quarantine_orders (null rows)
      → fact_orders (with revenue) → dim_products, dim_dates → daily_revenue view

    Returns:
        dict with keys: fact_rows, quarantined, deduped
    """
    # TODO: implement in Phase 4
    raise NotImplementedError
