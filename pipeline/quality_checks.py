# pipeline/quality_checks.py
# 5 data-quality checks run after ingestion, before transformation.
# Each check returns: {name, status, details, rows_affected}
# All results are persisted to the dq_results table in DuckDB for the dashboard.

import duckdb
from datetime import datetime, date

STATUS_PASS = "PASS"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"

# Expected columns in raw_orders (excluding metadata columns)
EXPECTED_COLUMNS = [
    "order_id", "order_timestamp", "customer_id", "product_id",
    "product_name", "category", "qty", "unit_price", "discount_pct", "region"
]

CRITICAL_NULL_COLS = ["order_id", "customer_id", "qty", "unit_price", "discount_pct"]
NULL_SPIKE_THRESHOLD = 0.05   # 5% — flag anything above this
ROW_MIN = 5_000
ROW_MAX = 10_000


def _result(name: str, status: str, details: str, rows_affected: int) -> dict:
    """Helper to build a standardized check result dict."""
    return {
        "name":          name,
        "status":        status,
        "details":       details,
        "rows_affected": rows_affected,
    }


def check_row_counts(con: duckdb.DuckDBPyConnection) -> dict:
    """
    Check that each source file has between ROW_MIN and ROW_MAX rows.
    Flags days outside the expected 5,000–10,000 range.
    """
    rows = con.execute("""
        SELECT _source_file, COUNT(*) AS cnt
        FROM raw_orders
        GROUP BY _source_file
        ORDER BY _source_file
    """).fetchall()

    outside = [(f, c) for f, c in rows if c < ROW_MIN or c > ROW_MAX]

    if outside:
        detail = "; ".join(f"{f}: {c:,} rows" for f, c in outside)
        return _result(
            "row_counts", STATUS_WARN,
            f"{len(outside)} file(s) outside {ROW_MIN:,}–{ROW_MAX:,} range: {detail}",
            sum(c for _, c in outside)
        )

    total = sum(c for _, c in rows)
    return _result(
        "row_counts", STATUS_PASS,
        f"All {len(rows)} files within {ROW_MIN:,}–{ROW_MAX:,} rows. Total: {total:,}",
        total
    )


def check_schema(con: duckdb.DuckDBPyConnection) -> dict:
    """
    Verify all expected columns exist in raw_orders.
    Column normalization happens in ingest.py; this is a post-load sanity check.
    """
    actual_cols = [row[0] for row in con.execute("DESCRIBE raw_orders").fetchall()]
    missing = [c for c in EXPECTED_COLUMNS if c not in actual_cols]

    if missing:
        return _result(
            "schema", STATUS_FAIL,
            f"Missing expected columns in raw_orders: {missing}",
            0
        )

    return _result(
        "schema", STATUS_PASS,
        f"All {len(EXPECTED_COLUMNS)} expected columns present in raw_orders",
        0
    )


def check_duplicates(con: duckdb.DuckDBPyConnection) -> dict:
    """
    Count order_ids that appear more than once across all files.
    Expected cause: sales_2025-03-15.csv is a re-delivery of March 14's data.
    """
    result = con.execute("""
        SELECT COUNT(*) AS dup_ids, SUM(cnt - 1) AS excess_rows
        FROM (
            SELECT order_id, COUNT(*) AS cnt
            FROM raw_orders
            WHERE order_id IS NOT NULL
            GROUP BY order_id
            HAVING COUNT(*) > 1
        ) dups
    """).fetchone()

    dup_ids, excess_rows = result
    dup_ids    = dup_ids    or 0
    excess_rows = excess_rows or 0

    if dup_ids > 0:
        # Find which files contain the duplicate order_ids
        files = con.execute("""
            SELECT DISTINCT r._source_file
            FROM raw_orders r
            INNER JOIN (
                SELECT order_id
                FROM raw_orders
                WHERE order_id IS NOT NULL
                GROUP BY order_id
                HAVING COUNT(*) > 1
            ) dups USING (order_id)
            ORDER BY r._source_file
        """).fetchall()
        file_list = ", ".join(f[0] for f in files)

        return _result(
            "duplicates", STATUS_WARN,
            f"{dup_ids:,} duplicate order_id(s), {excess_rows:,} excess rows. "
            f"Files involved: {file_list}",
            excess_rows
        )

    return _result(
        "duplicates", STATUS_PASS,
        "No duplicate order_ids found across all files",
        0
    )


def check_date_completeness(con: duckdb.DuckDBPyConnection) -> dict:
    """
    Verify that every date from 2025-03-01 to 2025-03-31 has at least one file loaded.
    Flags missing dates (expected: March 31 is missing from this dataset).
    """
    loaded_dates = {
        row[0] for row in
        con.execute("SELECT DISTINCT _file_date FROM raw_orders").fetchall()
    }

    expected_dates = {
        date(2025, 3, d) for d in range(1, 32)
    }
    missing = sorted(expected_dates - loaded_dates)

    if missing:
        missing_str = ", ".join(str(d) for d in missing)
        return _result(
            "date_completeness", STATUS_WARN,
            f"{len(missing)} date(s) missing from raw_orders: {missing_str}",
            len(missing)
        )

    return _result(
        "date_completeness", STATUS_PASS,
        f"All 31 March 2025 dates present in raw_orders",
        0
    )


def check_null_rates(con: duckdb.DuckDBPyConnection) -> dict:
    """
    Flag any file where a critical column exceeds NULL_SPIKE_THRESHOLD (5%) nulls.
    Checks per-file null rates — a spike in one file can be hidden in the overall average.
    Expected: sales_2025-03-26.csv has ~35% null unit_price and ~20% null product_name.
    """
    # Build per-file null rates for every critical column in one query
    col_cases = ", ".join(
        f"ROUND(100.0 * SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS {c}_null_pct"
        for c in CRITICAL_NULL_COLS
    )
    col_counts = ", ".join(
        f"SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END) AS {c}_nulls"
        for c in CRITICAL_NULL_COLS
    )

    per_file = con.execute(f"""
        SELECT _source_file, COUNT(*) AS total_rows, {col_cases}, {col_counts}
        FROM raw_orders
        GROUP BY _source_file
        ORDER BY _source_file
    """).fetchall()

    # Column positions in the result tuple
    n_cols = len(CRITICAL_NULL_COLS)
    # per_file row layout: [_source_file, total_rows, pct_0..pct_n, cnt_0..cnt_n]
    pct_start = 2
    cnt_start = 2 + n_cols

    issues = []
    total_null_rows = 0

    for row in per_file:
        fname = row[0]
        for i, col in enumerate(CRITICAL_NULL_COLS):
            pct = row[pct_start + i] or 0.0
            cnt = row[cnt_start + i] or 0
            if pct > NULL_SPIKE_THRESHOLD * 100:   # pct is already a percentage (e.g. 35.0)
                issues.append(f"{fname} / {col}: {pct}% null ({cnt:,} rows)")
                total_null_rows += cnt

    if issues:
        return _result(
            "null_rates", STATUS_WARN,
            f"Per-file null spike (>{NULL_SPIKE_THRESHOLD:.0%}) in "
            f"{len(issues)} column(s): " + " | ".join(issues),
            total_null_rows
        )

    return _result(
        "null_rates", STATUS_PASS,
        f"All critical columns below {NULL_SPIKE_THRESHOLD:.0%} null per file",
        0
    )


def run_all_checks(con: duckdb.DuckDBPyConnection) -> list:
    """
    Run all 5 DQ checks, persist results to dq_results table, return list of result dicts.

    The dq_results table is created fresh on each run (idempotent).
    The dashboard reads from this table for the DQ Status tab.
    """
    # Create dq_results table (idempotent)
    con.execute("""
        DROP TABLE IF EXISTS dq_results;
        CREATE TABLE dq_results (
            check_name    VARCHAR,
            status        VARCHAR,
            details       VARCHAR,
            rows_affected INTEGER,
            run_timestamp TIMESTAMP
        )
    """)

    run_ts = datetime.now()

    checks = [
        check_row_counts,
        check_schema,
        check_duplicates,
        check_date_completeness,
        check_null_rates,
    ]

    results = []
    for check_fn in checks:
        r = check_fn(con)
        con.execute(
            "INSERT INTO dq_results VALUES (?, ?, ?, ?, ?)",
            [r["name"], r["status"], r["details"], r["rows_affected"], run_ts]
        )
        results.append(r)

    return results
