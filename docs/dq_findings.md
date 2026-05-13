# Data Quality Findings — EDA Results

All 4 DQ issues were discovered by running `notebooks/eda.py` against the 30 CSV files in `datasets/`.

---

## Issue 1: Duplication — Re-Delivered File

**Found in:** `sales_2025-03-14.csv` and `sales_2025-03-15.csv`

**What happened:** `sales_2025-03-15.csv` is a complete re-delivery of March 14's data. Both files contain the same 6,152 rows with identical `order_id` values (all prefixed `ORD20250314...`) and identical timestamps. March 15's actual orders are absent.

**Evidence:**
```
March 14 rows: 6,152
March 15 rows: 6,152
Overlapping order_ids: 6,152 (100% overlap)
```

**Impact:** Without deduplication, March 14's revenue would be double-counted. Total excess rows: 6,152.

**Pipeline response:** `sql/create_clean.sql` deduplicates on `order_id` using `ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY _load_timestamp DESC)`, keeping the latest-loaded copy and discarding duplicates. The `[TRANSFORM]` log reports how many rows were removed.

---

## Issue 2: Missing File — March 31

**Found:** `datasets/` contains 30 files (March 1–30). March 31 is absent. The `late_arrivals/` subfolder exists but is empty.

**Evidence:**
```
Expected dates (March 2025): 31
Dates with files:            30
Missing dates:               ['2025-03-31']
```

**Impact:** March 31's revenue (~7,000 orders, ~Rs. 350,000 estimated) is not included in any totals. The gap is visible on the dashboard's day-by-day bar chart.

**Pipeline response:** The DQ check `check_date_completeness` flags `2025-03-31` as WARN. The `late_arrivals/` directory is scanned at every pipeline run, so if the file is delivered later, the next run will pick it up automatically.

---

## Issue 3: Schema Drift — `sales_2025-03-22.csv`

**Found in:** `sales_2025-03-22.csv` only.

**What happened:** The upstream system sent a different schema on March 22:

| Column (actual) | Column (expected) | Action |
|-----------------|-------------------|--------|
| `item_name` | `product_name` | Renamed to `product_name` |
| `channel` | *(not in schema)* | Dropped before loading |

**Evidence:**
```
Actual columns:   ['order_id', 'order_timestamp', 'customer_id', 'product_id',
                   'item_name', 'category', 'qty', 'unit_price', 'discount_pct',
                   'region', 'channel']
Expected columns: ['order_id', 'order_timestamp', 'customer_id', 'product_id',
                   'product_name', 'category', 'qty', 'unit_price', 'discount_pct', 'region']
```

**Impact:** If loaded as-is, `product_name` would be NULL for all March 22 rows (7,142 rows). The `channel` column would cause a schema mismatch at INSERT time.

**Pipeline response:** `pipeline/ingest.py` normalizes columns before loading: `item_name` → `product_name`, unknown columns dropped. The DQ check `check_schema` logs a WARN for this file. March 22's data loads cleanly after normalization.

---

## Issue 4: Null Spike — `sales_2025-03-26.csv`

**Found in:** `sales_2025-03-26.csv` (6,415 rows).

**What happened:** Two critical columns have abnormally high null rates in this file:

| Column | Null Rate | Null Rows |
|--------|-----------|-----------|
| `product_name` | 20.0% | 1,283 rows |
| `unit_price` | 35.0% | 2,245 rows |

**Impact:** Rows with null `unit_price` cannot have revenue calculated — they must be excluded. Rows with null `product_name` alone are not critical (product_id is still present), but they reduce dashboard completeness.

**Pipeline response:**
- Rows where `unit_price IS NULL` (critical for revenue) are moved to `quarantine_orders` and excluded from `fact_orders`.
- The DQ check `check_null_rates` flags `sales_2025-03-26.csv` as WARN with exact counts.
- The dashboard DQ tab shows quarantined row counts per day.

**Estimated revenue impact:** ~2,245 rows × avg ~Rs. 100 order value = ~Rs. 224,500 excluded from totals.

---

## Summary Table

| Issue | File(s) | Rows Affected | Pipeline Action | DQ Status |
|-------|---------|---------------|-----------------|-----------|
| Duplication | sales_2025-03-15.csv | 6,152 | Deduplicate (keep latest) | WARN |
| Missing file | sales_2025-03-31.csv | ~7,000 (entire day) | Flag missing date | WARN |
| Schema drift | sales_2025-03-22.csv | 7,142 (entire file) | Rename + drop columns | WARN |
| Null spike | sales_2025-03-26.csv | 2,245 (unit_price null) | Quarantine null rows | WARN |
