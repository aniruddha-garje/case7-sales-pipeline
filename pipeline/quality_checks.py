# pipeline/quality_checks.py
# 5 data-quality checks run after ingestion, before transformation.
# Each check returns a structured dict: {name, status, details, rows_affected}
# Results are stored in the dq_results table in DuckDB.

import duckdb
from datetime import datetime


STATUS_PASS = "PASS"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"


def check_row_counts(con: duckdb.DuckDBPyConnection) -> dict:
    """Flag any day with fewer than 5,000 or more than 10,000 rows."""
    # TODO: implement in Phase 3
    raise NotImplementedError


def check_schema(con: duckdb.DuckDBPyConnection) -> dict:
    """Verify all expected columns exist in raw_orders."""
    # TODO: implement in Phase 3
    raise NotImplementedError


def check_duplicates(con: duckdb.DuckDBPyConnection) -> dict:
    """Count order_ids that appear more than once across all files."""
    # TODO: implement in Phase 3
    raise NotImplementedError


def check_date_completeness(con: duckdb.DuckDBPyConnection) -> dict:
    """Verify every date in March 2025 has at least one file loaded."""
    # TODO: implement in Phase 3
    raise NotImplementedError


def check_null_rates(con: duckdb.DuckDBPyConnection) -> dict:
    """Flag any critical column with a null rate above 2%."""
    # TODO: implement in Phase 3
    raise NotImplementedError


def run_all_checks(con: duckdb.DuckDBPyConnection) -> list:
    """
    Run all 5 DQ checks and persist results to the dq_results table.

    Returns:
        List of result dicts (one per check).
    """
    # TODO: implement in Phase 3
    raise NotImplementedError
