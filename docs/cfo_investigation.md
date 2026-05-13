# If Monday's Revenue Changed by 3% — Investigation Runbook

**Time budget: 10 minutes.**
**Audience:** CFO / data analyst investigating a revenue discrepancy.

---

## Step 1: Check the DQ Dashboard (2 min)

Open the Streamlit dashboard → **Data Quality** tab.

Look for any ⚠️ WARN or ❌ FAIL checks. If a check failed since the last run, that is almost certainly the explanation. Common culprits:

- **Duplicate check WARN** → double-counted rows in previous run, now deduped
- **Date completeness WARN** → a file arrived late and was now included
- **Null rate WARN** → rows were quarantined (excluded from revenue) or un-quarantined

---

## Step 2: Check for Late Files (2 min)

A file delivered late to `late_arrivals/` would add revenue retroactively.

```sql
SELECT _source_file, COUNT(*) AS rows, MIN(order_timestamp), MAX(order_timestamp)
FROM fact_orders
GROUP BY _source_file
ORDER BY _source_file;
```

If any `_source_file` comes from `late_arrivals/`, those orders were missing in the previous run.

---

## Step 3: Check Row Counts by Day (2 min)

```sql
SELECT order_date, COUNT(*) AS orders, ROUND(SUM(revenue), 2) AS daily_revenue
FROM fact_orders
GROUP BY order_date
ORDER BY order_date;
```

Compare against the previous pipeline run (check logs or dashboard history).
- A missing row → a missing day's file; now delivered → big revenue jump
- An extra day → previously missing file now included

---

## Step 4: Check for New Duplicates (2 min)

If a file was re-delivered (re-sent by upstream), duplicate order_ids may have appeared.

```sql
SELECT order_id, COUNT(*) AS occurrences
FROM raw_orders
GROUP BY order_id
HAVING COUNT(*) > 1
ORDER BY occurrences DESC
LIMIT 20;
```

High duplicate counts in a specific date range → that date's file was re-sent.

---

## Step 5: Check Quarantine Impact (2 min)

Quarantined rows are excluded from revenue. If a null spike was fixed upstream,
those rows now count → revenue increases. Conversely, a new null spike → revenue drops.

```sql
SELECT _file_date, COUNT(*) AS quarantined_rows
FROM quarantine_orders
GROUP BY _file_date
ORDER BY _file_date;
```

Compare quarantine counts between the current run and the previous run.

---

## Root Cause Decision Tree

```
Revenue INCREASED?
├── Late file now present?    → YES → late_arrivals/ file added orders for a missing day
├── Duplicate count DECREASED? → YES → dedup previously missed some; now fixed
└── Quarantine count DECREASED? → YES → null spike was fixed upstream; rows re-included

Revenue DECREASED?
├── Missing date in fact_orders? → YES → file not delivered; check datasets/ folder
├── Duplicate count INCREASED?  → YES → re-delivered file added dupe rows that got deduped
└── Quarantine count INCREASED? → YES → new null spike in latest file; check quality_checks log
```

---

## How to Re-Run the Pipeline

```bash
python pipeline/run_pipeline.py
```

The pipeline is idempotent — safe to re-run. It will produce an identical result on identical input.
