# CLAUDE.md — Case 7: Streaming Sales Pipeline — From CSV Chaos to a Trusted Dashboard

## PROJECT OVERVIEW

An e-commerce startup dumps daily sales CSVs into a shared folder. Different teams report wildly different revenue numbers. Build a pipeline that produces ONE trusted number, prove it's trustworthy, and give the CFO a dashboard she can rely on.

**Dataset:** 30 daily CSV files (March 2025), ~5,000–10,000 rows/day, ~19 MB total.
**Contains 4 INTENTIONAL data-quality issues:** duplication, missing/late files, schema drift, null spikes.
**Hardware:** Windows 11, any machine. No GPU needed. Everything runs locally.

---

## TECH STACK (LOCKED)

| Layer | Tool | Why |
|-------|------|-----|
| Ingestion | Python + glob + pandas | 30 static CSVs don't need an orchestrator |
| DQ Checks | Custom Python (no Great Expectations — overkill for 4-5 checks) | Evaluators see YOUR logic, not a library's |
| Warehouse | DuckDB (embedded, zero config) | Reads CSVs natively, SQL interface, free |
| Transforms | SQL via DuckDB | Clean, readable, evaluator-friendly |
| Dashboard | Streamlit + Plotly | Free HF Spaces deployment, fast to build |
| Deployment | Hugging Face Spaces (Streamlit SDK) | Free tier, auto-builds from git push |

### Why NOT Airflow/Prefect/Dagster (document in DECISIONS.md):
> "The pipeline processes 30 static CSV files in a one-shot batch run. Orchestrator overhead (server process, DAG definitions, scheduler) is not justified for this workload. Each pipeline step is an idempotent Python function with structured logging. In production with daily arriving files, I'd use Prefect with scheduled flows and retries."

### Why NOT dbt (document in DECISIONS.md):
> "dbt adds project scaffolding (profiles.yml, dbt_project.yml, models/) that's disproportionate for 3-4 SQL transforms. Raw SQL in DuckDB achieves the same result with less abstraction. In production with 50+ models, dbt's lineage tracking and testing framework would be worth the setup cost."

---

## THE 4 HIDDEN DQ ISSUES (discover these during EDA)

The brief says: "4 intentional issues spanning duplication, missing/late files, schema drift, and null spikes."

1. **DUPLICATION** — Some `order_id` values appear more than once (same file or across files). Pipeline must dedup on `order_id`.

2. **MISSING/LATE FILES** — `late_arrivals/sales_2025-03-18.csv` is NOT in the main folder. March has 31 days, the folder says "30 daily files" but there might be a gap. Must scan BOTH directories. Must check date completeness.

3. **SCHEMA DRIFT** — One or more files may have different column names, missing columns, extra columns, or type changes. Must validate schema before loading.

4. **NULL SPIKES** — One or more files have abnormally high null rates in a critical column (likely `order_value`, `customer_id`, or `product_id`). Must detect and flag.

### How to find them:
```python
# In EDA phase, run these checks across all 30+ files:

# 1. Duplication
df.groupby('order_id').size().reset_index(name='count').query('count > 1')

# 2. File completeness
expected_dates = pd.date_range('2025-03-01', '2025-03-31')
actual_dates = [extract_date_from_filename(f) for f in all_files]
missing = set(expected_dates) - set(actual_dates)

# 3. Schema drift
expected_cols = ['order_id', 'order_timestamp', 'customer_id', 'product_id',
                 'product_name', 'category', 'qty', 'unit_price', 'discount_pct', 'region']
for f in files:
    df = pd.read_csv(f, nrows=0)
    if list(df.columns) != expected_cols:
        print(f"SCHEMA DRIFT in {f}: {df.columns.tolist()}")

# 4. Null spikes
for f in files:
    df = pd.read_csv(f)
    null_pct = df.isnull().mean()
    high_nulls = null_pct[null_pct > 0.05]  # >5% nulls is suspicious
    if len(high_nulls) > 0:
        print(f"NULL SPIKE in {f}: {high_nulls.to_dict()}")
```

---

## PROJECT STRUCTURE

```
case7-sales-pipeline/
├── CLAUDE.md
├── README.md
├── DECISIONS.md
├── requirements.txt
├── .gitignore
│
├── pipeline/
│   ├── __init__.py
│   ├── ingest.py              # Scan folders, load CSVs, land in DuckDB raw table
│   ├── quality_checks.py      # 5 DQ checks, returns pass/fail + details
│   ├── transform.py           # Raw → clean → modeled (fact_orders, dim_products)
│   └── run_pipeline.py        # Main entry: ingest → check → transform → export
│
├── dashboard/
│   ├── app.py                 # Streamlit app (3 views)
│   └── requirements.txt       # For HF Spaces
│
├── sql/
│   ├── create_raw.sql         # Raw table DDL
│   ├── create_clean.sql       # Deduped + null-handled table
│   ├── fact_orders.sql        # Fact table with calculated revenue
│   ├── dim_products.sql       # Product dimension
│   ├── dim_dates.sql          # Date dimension
│   └── daily_revenue.sql      # Aggregated view for dashboard
│
├── docs/
│   ├── data_contract.md       # REQUIRED: input schema + break handling
│   ├── cfo_investigation.md   # REQUIRED: "trace the 3% change in 10 min"
│   ├── dq_findings.md         # What 4 issues found + how handled
│   └── data_lineage.md        # Mermaid diagram (stretch)
│
├── datasets/                  # The provided CSVs
│   └── case7_daily_sales/
│       ├── sales_2025-03-01.csv
│       ├── ... (29 files in main)
│       └── late_arrivals/
│           └── sales_2025-03-18.csv
│
├── output/
│   └── sales.duckdb           # Generated warehouse file
│
├── deck/
│   └── deck.pdf
│
└── demo_video_link.txt
```

---

## DATASET SCHEMA (expected, from the brief)

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| order_id | string | ORD2025030100000 | Should be unique per order |
| order_timestamp | string (ISO) | 2025-03-01T21:16:23 | Parse to datetime |
| customer_id | string | C19187 | |
| product_id | string | P002 | 12 unique products |
| product_name | string | USB-C Cable | 12 unique |
| category | string | Electronics | 5 unique categories |
| qty | int | 3 | 1-5 range |
| unit_price | float | 13.76 | Varies |
| discount_pct | float | 0.0 | 0, 0.05, 0.10, 0.15 |
| region | string | North | 4 regions |

**Derived field (YOU calculate):**
```sql
revenue = qty * unit_price * (1 - discount_pct)
```

---

## PIPELINE LOGIC (step by step)

### Step 1: Ingest (ingest.py)
```python
def ingest(db_path, data_dir):
    """
    Scan BOTH main folder and late_arrivals/ subfolder.
    Load each CSV into a DuckDB 'raw_orders' table.
    Tag each row with source_file and load_timestamp for lineage.
    """
    # CRITICAL: scan both directories
    main_files = glob.glob(os.path.join(data_dir, "sales_*.csv"))
    late_files = glob.glob(os.path.join(data_dir, "late_arrivals", "sales_*.csv"))
    all_files = main_files + late_files

    for f in all_files:
        df = pd.read_csv(f)
        df['_source_file'] = os.path.basename(f)
        df['_load_timestamp'] = datetime.now().isoformat()
        # Append to DuckDB raw_orders table
```

Key design: add `_source_file` and `_load_timestamp` metadata columns. These enable the CFO investigation ("which file did this row come from?").

### Step 2: Quality Checks (quality_checks.py)
Run 5 checks AFTER ingestion, BEFORE transformation:

```python
def run_all_checks(con) -> dict:
    results = {}
    results['row_count'] = check_row_counts(con)        # expected: 5k-10k per day
    results['schema'] = check_schema_consistency(con)     # all expected columns present
    results['duplicates'] = check_duplicates(con)         # order_id uniqueness
    results['freshness'] = check_date_completeness(con)   # all March dates covered
    results['null_rates'] = check_null_spikes(con)        # no column >5% null
    return results
```

Each check returns: `{check_name, status: PASS/WARN/FAIL, details: str, rows_affected: int}`

Store results in a `dq_results` table in DuckDB — the dashboard reads this.

### Step 3: Transform (transform.py)
```sql
-- Step 3a: Deduplicate
CREATE TABLE clean_orders AS
SELECT DISTINCT ON (order_id) *
FROM raw_orders
ORDER BY order_id, _load_timestamp DESC;  -- latest load wins

-- Step 3b: Handle nulls (drop or flag rows with null order_value/qty)
-- Log dropped rows to a quarantine table

-- Step 3c: Calculate revenue
CREATE TABLE fact_orders AS
SELECT
    order_id,
    CAST(order_timestamp AS TIMESTAMP) as order_timestamp,
    DATE_TRUNC('day', CAST(order_timestamp AS TIMESTAMP)) as order_date,
    customer_id,
    product_id,
    product_name,
    category,
    qty,
    unit_price,
    discount_pct,
    region,
    ROUND(qty * unit_price * (1 - discount_pct), 2) as revenue,
    _source_file
FROM clean_orders
WHERE order_id IS NOT NULL
  AND qty IS NOT NULL
  AND unit_price IS NOT NULL;

-- Step 3d: Dimension tables
CREATE TABLE dim_products AS
SELECT DISTINCT product_id, product_name, category
FROM fact_orders;

CREATE TABLE dim_dates AS
SELECT DISTINCT
    order_date,
    EXTRACT(DOW FROM order_date) as day_of_week,
    EXTRACT(DAY FROM order_date) as day_of_month,
    CASE WHEN EXTRACT(DOW FROM order_date) IN (0, 6) THEN TRUE ELSE FALSE END as is_weekend
FROM fact_orders;
```

### Step 4: Dashboard (dashboard/app.py)
Three tabs/views:

**View 1: Daily Revenue**
- Line chart of daily revenue over March 2025
- Total revenue KPI card
- Revenue by region (stacked bar)

**View 2: Top Products**
- Revenue by product (horizontal bar)
- Revenue by category (pie/donut)
- Top 10 customers by spend

**View 3: DQ Status** ← easy to forget, REQUIRED
- Table showing each DQ check: name, status (✅/⚠️/❌), details
- Row counts per day (bar chart — gaps = missing days)
- Null rates per column per day (heatmap)
- Duplicate count

---

## REQUIRED DOCUMENTS (do NOT skip these)

### data_contract.md
```markdown
# Data Contract — Daily Sales CSV

## Source
E-commerce order system, delivered as daily CSV files.

## Delivery
- One file per day: `sales_YYYY-MM-DD.csv`
- Delivered to `datasets/case7_daily_sales/` by midnight UTC
- Late files may appear in `late_arrivals/` subfolder

## Schema
| Column | Type | Nullable | Constraints |
|--------|------|----------|------------|
| order_id | string | No | Unique across all files |
| order_timestamp | ISO 8601 | No | Must fall within file's date |
| customer_id | string | No | Format: C##### |
| product_id | string | No | Must exist in product catalog |
| product_name | string | No | |
| category | string | No | One of: Electronics, Apparel, Grocery, Stationery, Home & Kitchen |
| qty | integer | No | 1-10 |
| unit_price | float | No | > 0 |
| discount_pct | float | No | 0.0 to 0.50 |
| region | string | No | One of: North, South, East, West |

## Quality Expectations
- Row count: 5,000–10,000 per file
- Null rate: <1% for any column
- Duplicate order_ids: 0 within a file, 0 across files
- Schema: columns must match exactly (name, order, count)

## When Contract Breaks
| Violation | Pipeline Behavior |
|-----------|------------------|
| Missing file for a date | Log WARNING, continue, flag on dashboard |
| Schema mismatch | REJECT file, log ERROR, alert |
| Duplicate order_ids | Deduplicate (keep latest load), log WARNING |
| Null spike (>5%) | Load but QUARANTINE null rows, log WARNING |
| Row count outside range | Log WARNING, investigate |
```

### cfo_investigation.md
```markdown
# If Monday's Revenue Changed by 3% — Investigation Runbook

**Time budget: 10 minutes.**

## Step 1: Check DQ Dashboard (2 min)
Open the dashboard → DQ Status tab. Look for any ⚠️ or ❌.
If a check failed, that's likely your answer.

## Step 2: Check for Late Files (2 min)
```sql
SELECT _source_file, COUNT(*), MIN(order_timestamp), MAX(order_timestamp)
FROM fact_orders
GROUP BY _source_file
ORDER BY _source_file;
```
Look for files from `late_arrivals/`. A late file adds revenue retroactively.

## Step 3: Check Row Counts by Day (2 min)
```sql
SELECT order_date, COUNT(*) as orders, SUM(revenue) as daily_revenue
FROM fact_orders
GROUP BY order_date
ORDER BY order_date;
```
Compare against previous run. A missing or extra day = big revenue swing.

## Step 4: Check for New Duplicates (2 min)
```sql
SELECT order_id, COUNT(*) as dupes
FROM raw_orders
GROUP BY order_id
HAVING COUNT(*) > 1;
```
If a file was re-delivered, duplicates may have slipped in.

## Step 5: Check Null Impact (2 min)
```sql
SELECT order_date, COUNT(*) as quarantined_rows
FROM quarantine_orders
GROUP BY order_date
ORDER BY order_date;
```
Quarantined rows = revenue excluded. If null spike was fixed upstream,
those rows now count → revenue increases.

## Root Cause Decision Tree
- Revenue UP + new late file → late file added orders
- Revenue DOWN + missing day → file not delivered
- Revenue changed + duplicate count changed → dedup logic affected
- Revenue changed + quarantine count changed → null handling affected
```

---

## GIT COMMIT PLAN (13+ commits)

1. `init: project scaffold, README, DECISIONS.md, requirements.txt`
2. `data: add dataset files and document schema`
3. `feat: EDA notebook — explore all files, discover DQ issues`
4. `feat: ingest.py — scan both folders, load to DuckDB raw table`
5. `feat: quality_checks.py — 5 DQ checks with structured results`
6. `feat: transform.py — dedup, null handling, fact_orders, dimensions`
7. `feat: run_pipeline.py — end-to-end orchestration with logging`
8. `feat: Streamlit dashboard — daily revenue and top products views`
9. `feat: dashboard DQ status view with check results`
10. `docs: data_contract.md`
11. `docs: cfo_investigation.md and dq_findings.md`
12. `docs: data lineage diagram (Mermaid)`
13. `deploy: HF Spaces config and deployment`
14. `docs: 5-slide deck`
15. `final: README polish, submission-ready`

---

## IDEMPOTENCY (stretch goal, implement from the start)

The pipeline must be safe to re-run:
```python
# In ingest.py: DROP TABLE IF EXISTS before loading
con.execute("DROP TABLE IF EXISTS raw_orders")

# In transform.py: DROP and recreate all derived tables
con.execute("DROP TABLE IF EXISTS clean_orders")
con.execute("DROP TABLE IF EXISTS fact_orders")
```

This means: run the pipeline twice → same result. No double-counting.
Document this in DECISIONS.md.

---

## DEPLOYMENT TO HUGGING FACE SPACES

Create `dashboard/requirements.txt`:
```
streamlit
pandas
duckdb
plotly
```

Create `dashboard/README.md` (HF Spaces reads this):
```yaml
---
title: Case 7 Sales Dashboard
emoji: 📊
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: 1.36.0
app_file: app.py
pinned: false
---
```

The dashboard reads from a pre-built `sales.duckdb` file (generated by the pipeline, committed to the repo). HF Spaces just serves the Streamlit app — no pipeline runs on their servers.

---

## KNOWN LIMITATIONS (document in DECISIONS.md)

1. Pipeline runs as a one-shot batch, not scheduled. In production: Prefect with daily cron.
2. DuckDB is single-file, single-writer. In production: Postgres or BigQuery for concurrent access.
3. No alerting — DQ failures are logged and shown on dashboard but don't send notifications. In production: Slack/email alerts via Prefect.
4. No SCD2 on products — product dimension is latest-state only. In production: add effective_from/effective_to columns.
