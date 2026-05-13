# pipeline/transform.py
# Transforms raw_orders through clean_orders → fact_orders + dimension tables.
# All heavy logic lives in sql/*.sql files; Python just orchestrates and logs.
#
# Transform chain:
#   raw_orders
#     → clean_orders    (dedup on order_id, last-write-wins)
#     → quarantine_orders (rows with null critical fields)
#     → fact_orders     (revenue calculated, only clean non-null rows)
#     → dim_products, dim_dates, daily_revenue view

import os
import duckdb


def load_sql(filename: str) -> str:
    """Load a SQL file from the sql/ directory (relative to project root)."""
    sql_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")
    with open(os.path.join(sql_dir, filename), "r") as f:
        return f.read()


def create_quarantine(con: duckdb.DuckDBPyConnection) -> int:
    """
    Move rows from clean_orders where critical fields are NULL into quarantine_orders.
    These rows are excluded from fact_orders and therefore from all revenue calculations.

    Returns the number of quarantined rows.
    """
    con.execute("""
        DROP TABLE IF EXISTS quarantine_orders;
        CREATE TABLE quarantine_orders AS
        SELECT *, 'null_critical_field' AS _quarantine_reason
        FROM clean_orders
        WHERE qty IS NULL
           OR unit_price IS NULL
           OR discount_pct IS NULL
    """)
    quarantined = con.execute("SELECT COUNT(*) FROM quarantine_orders").fetchone()[0]
    return quarantined


def transform_all(con: duckdb.DuckDBPyConnection) -> dict:
    """
    Run the full transformation chain. All steps are idempotent (DROP IF EXISTS).

    Returns:
        dict: {raw_rows, clean_rows, deduped, quarantined, fact_rows}
    """
    raw_rows = con.execute("SELECT COUNT(*) FROM raw_orders").fetchone()[0]
    print(f"[TRANSFORM] raw_orders: {raw_rows:,} rows")

    # Step 1: Deduplicate — keep one row per order_id (latest _load_timestamp wins)
    print("[TRANSFORM] Deduplicating raw_orders -> clean_orders ...")
    con.execute(load_sql("create_clean.sql"))
    clean_rows = con.execute("SELECT COUNT(*) FROM clean_orders").fetchone()[0]
    deduped = raw_rows - clean_rows
    print(f"[TRANSFORM] clean_orders: {clean_rows:,} rows ({deduped:,} duplicates removed)")

    # Step 2: Quarantine rows with null critical fields
    print("[TRANSFORM] Quarantining rows with null critical fields ...")
    quarantined = create_quarantine(con)
    if quarantined > 0:
        # Show which file(s) the quarantined rows came from
        by_file = con.execute("""
            SELECT _source_file, COUNT(*) AS cnt
            FROM quarantine_orders
            GROUP BY _source_file
            ORDER BY cnt DESC
        """).fetchall()
        for fname, cnt in by_file:
            print(f"  [TRANSFORM] Quarantined {cnt:,} rows from {fname}")
    print(f"[TRANSFORM] quarantine_orders: {quarantined:,} rows total")

    # Step 3: Build fact_orders (revenue calculation, clean non-null rows only)
    print("[TRANSFORM] Building fact_orders (with calculated revenue) ...")
    con.execute(load_sql("fact_orders.sql"))
    fact_rows = con.execute("SELECT COUNT(*) FROM fact_orders").fetchone()[0]
    print(f"[TRANSFORM] fact_orders: {fact_rows:,} rows")

    # Verify: raw = clean + quarantined (within dedup adjustment)
    # fact_rows should == clean_rows - quarantined
    expected_fact = clean_rows - quarantined
    if fact_rows != expected_fact:
        print(f"[TRANSFORM] WARNING: expected {expected_fact:,} fact rows "
              f"but got {fact_rows:,} — check for additional nulls on order_id")

    # Step 4: Dimension tables
    print("[TRANSFORM] Building dimension tables ...")
    con.execute(load_sql("dim_products.sql"))
    n_products = con.execute("SELECT COUNT(*) FROM dim_products").fetchone()[0]
    print(f"[TRANSFORM] dim_products: {n_products} products")

    con.execute(load_sql("dim_dates.sql"))
    n_dates = con.execute("SELECT COUNT(*) FROM dim_dates").fetchone()[0]
    print(f"[TRANSFORM] dim_dates: {n_dates} dates")

    # Step 5: Aggregated view for the dashboard
    con.execute(load_sql("daily_revenue.sql"))
    print("[TRANSFORM] Created daily_revenue view")

    return {
        "raw_rows":   raw_rows,
        "clean_rows": clean_rows,
        "deduped":    deduped,
        "quarantined": quarantined,
        "fact_rows":  fact_rows,
    }
