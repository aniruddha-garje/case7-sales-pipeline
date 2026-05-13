# Data Quality Findings — EDA Results

> This document will be completed after Phase 1 (EDA) confirms the exact nature of each issue.

## Issue 1: Duplication

**Expected:** Each `order_id` appears exactly once across all files.
**Found:** TBD — will document after EDA run.
**Pipeline response:** `clean_orders` deduplicates on `order_id`, keeping the row with the latest `_load_timestamp`.

---

## Issue 2: Missing / Late File

**Expected:** One file per day for all 31 days of March 2025.
**Found:** TBD — will document after EDA run.
**Pipeline response:** Ingestion scans both `datasets/` and `datasets/late_arrivals/`. The DQ check flags any missing dates.

---

## Issue 3: Schema Drift

**Expected:** All files have the same 10 columns in the same order.
**Found:** TBD — will document after EDA run.
**Pipeline response:** `ingest.py` normalizes column names before loading. If a file cannot be normalized, it is rejected with a logged ERROR.

---

## Issue 4: Null Spike

**Expected:** Null rate < 1% for all columns in all files.
**Found:** TBD — will document after EDA run.
**Pipeline response:** Rows with nulls in critical columns (`order_id`, `qty`, `unit_price`, `discount_pct`) are moved to `quarantine_orders` and excluded from `fact_orders`.
