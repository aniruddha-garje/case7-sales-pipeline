# pipeline/run_pipeline.py
# Main entry point — orchestrates the full pipeline:
#   1. Ingest   — load all CSVs into DuckDB raw_orders
#   2. DQ Checks — run 5 quality checks, store results in dq_results
#   3. Transform — dedup, quarantine, build fact_orders + dimensions
#   4. Summary  — print totals, verify idempotency
#
# Run: python pipeline/run_pipeline.py

import os
import sys

# Add project root to path so pipeline/ imports resolve
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import duckdb
from pipeline.ingest import ingest_all
from pipeline.quality_checks import run_all_checks
from pipeline.transform import transform_all

DB_PATH  = os.path.join(ROOT, "output", "sales.duckdb")
DATA_DIR = os.path.join(ROOT, "datasets")

# Ensure output/ directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def main():
    print("=" * 60)
    print("SALES DATA PIPELINE -- Starting")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Step 1: Ingest
    # ------------------------------------------------------------------
    print()
    ingest_result = ingest_all(db_path=DB_PATH, data_dir=DATA_DIR)
    print(f"[PIPELINE] Ingested {ingest_result['total_rows']:,} rows "
          f"from {ingest_result['files_loaded']} files "
          f"({ingest_result['files_skipped']} skipped)")

    # ------------------------------------------------------------------
    # Step 2: Quality Checks  (run before transform so DQ is on raw data)
    # ------------------------------------------------------------------
    print()
    print("[PIPELINE] Running data quality checks ...")
    con = duckdb.connect(DB_PATH)
    dq_results = run_all_checks(con)

    any_fail = False
    for r in dq_results:
        icon = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]"}.get(r["status"], "[?]")
        print(f"[DQ] {icon} {r['name']:25s} rows_affected={r['rows_affected']:,}")
        print(f"       {r['details']}")
        if r["status"] == "FAIL":
            any_fail = True

    if any_fail:
        print("\n[PIPELINE] ERROR: One or more DQ checks FAILED. "
              "Review the issues above before proceeding.")
        con.close()
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 3: Transform
    # ------------------------------------------------------------------
    print()
    print("[PIPELINE] Running transformations ...")
    transform_result = transform_all(con)

    print()
    print(f"[PIPELINE] Transform complete:")
    print(f"  raw_orders:        {transform_result['raw_rows']:>10,} rows")
    print(f"  duplicates removed:{transform_result['deduped']:>10,} rows")
    print(f"  quarantined:       {transform_result['quarantined']:>10,} rows")
    print(f"  fact_orders:       {transform_result['fact_rows']:>10,} rows")

    # ------------------------------------------------------------------
    # Step 4: Summary
    # ------------------------------------------------------------------
    print()
    total_revenue = con.execute(
        "SELECT ROUND(SUM(revenue), 2) FROM fact_orders"
    ).fetchone()[0]

    total_orders = con.execute(
        "SELECT COUNT(*) FROM fact_orders"
    ).fetchone()[0]

    unique_customers = con.execute(
        "SELECT COUNT(DISTINCT customer_id) FROM fact_orders"
    ).fetchone()[0]

    avg_order = con.execute(
        "SELECT ROUND(AVG(revenue), 2) FROM fact_orders"
    ).fetchone()[0]

    print("=" * 60)
    print("MARCH 2025 PIPELINE SUMMARY")
    print("=" * 60)
    print(f"  Total Revenue:      Rs. {total_revenue:>14,.2f}")
    print(f"  Total Orders:            {total_orders:>14,}")
    print(f"  Unique Customers:        {unique_customers:>14,}")
    print(f"  Avg Order Value:    Rs. {avg_order:>14,.2f}")
    print("=" * 60)

    con.close()
    print(f"\n[PIPELINE] Database saved to: {DB_PATH}")
    print("[PIPELINE] Done. Run `streamlit run dashboard/app.py` to view the dashboard.")


if __name__ == "__main__":
    main()
