# Case 7: Streaming Sales Pipeline — From CSV Chaos to a Trusted Dashboard

> **Live Dashboard:** [Add Hugging Face Spaces URL here after deployment]
> **GitHub:** https://github.com/aniruddha-garje/case7-sales-pipeline

An e-commerce startup drops daily sales CSVs into a shared folder. Different teams report different revenue numbers. This pipeline produces **one trusted number**, proves it's trustworthy, and gives the CFO a dashboard she can rely on.

---

## Verified Pipeline Output

| Metric | Value |
|--------|-------|
| Total Revenue (March 2025) | **Rs. 10,276,245.96** |
| Total Orders | **205,903** |
| Unique Customers | **49,173** |
| Avg Order Value | **Rs. 49.91** |
| Raw rows ingested | 214,300 |
| Duplicates removed | 6,152 |
| Rows quarantined (null unit_price) | 2,245 |

---

## Problem Statement

- 30 daily CSV files for March 2025 (~5,000–10,000 rows/day, ~19 MB total)
- 4 intentional data-quality issues discovered during EDA: duplication, missing file, schema drift, null spike
- Goal: single clean fact table + live dashboard with full DQ transparency

---

## Tech Stack

| Layer | Tool | Why |
|-------|------|-----|
| Ingestion | Python + glob + pandas | Simple, readable, no orchestrator overhead |
| DQ Checks | Custom Python | Evaluators see the logic, not a library's |
| Warehouse | DuckDB | Embedded, zero config, SQL interface |
| Transforms | SQL via DuckDB | Clean, evaluator-friendly |
| Dashboard | Streamlit + Plotly | Fast to build, free HF Spaces deployment |
| Deployment | Hugging Face Spaces | Free tier, auto-builds from git push |

---

## The 4 DQ Issues Found (EDA → `notebooks/eda.py`)

| # | Issue | File | Impact | Fix |
|---|-------|------|--------|-----|
| 1 | **Duplication** | `sales_2025-03-15.csv` is a full re-delivery of March 14 | 6,152 excess rows | Dedup on `order_id`, keep latest `_load_timestamp` |
| 2 | **Missing file** | `sales_2025-03-31.csv` absent from all directories | Entire day of revenue missing | DQ check flags date gap; `late_arrivals/` scanned on every run |
| 3 | **Schema drift** | `sales_2025-03-22.csv` has `item_name` + extra `channel` col | Would break INSERT schema | Rename `item_name`→`product_name`, drop `channel` at ingest |
| 4 | **Null spike** | `sales_2025-03-26.csv`: `unit_price` 35% null (2,245 rows) | Revenue miscalculation | Quarantine null rows to `quarantine_orders`, exclude from revenue |

---

## How to Run Locally

### 1. Clone the repo
```bash
git clone https://github.com/aniruddha-garje/case7-sales-pipeline.git
cd case7-sales-pipeline
```

### 2. Set up Python environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 3. Run the full pipeline
```bash
python pipeline/run_pipeline.py
```

Output: `output/sales.duckdb` with all cleaned tables + DQ results.

### 4. Launch the dashboard
```bash
streamlit run dashboard/app.py
```

Opens at `http://localhost:8501`

### 5. (Optional) Run EDA to see DQ discovery
```bash
python notebooks/eda.py
```

### 6. (Optional) Query the database directly
```bash
venv\Scripts\python.exe -c "import duckdb; con=duckdb.connect('output/sales.duckdb'); print(con.execute('SELECT * FROM daily_revenue').df())"
```

---

## Project Structure

```
case7-sales-pipeline/
├── pipeline/
│   ├── ingest.py           # Scan both folders, load CSVs, normalize schema, tag lineage
│   ├── quality_checks.py   # 5 DQ checks → dq_results table
│   ├── transform.py        # Dedup + quarantine + fact/dim tables
│   └── run_pipeline.py     # End-to-end orchestration with logging
├── dashboard/
│   └── app.py              # Streamlit: Revenue / Products / DQ Status tabs
├── sql/
│   ├── create_raw.sql      # raw_orders DDL
│   ├── create_clean.sql    # Dedup logic
│   ├── fact_orders.sql     # Revenue calculation
│   ├── dim_products.sql    # Product dimension
│   ├── dim_dates.sql       # Date dimension
│   └── daily_revenue.sql   # Aggregated view
├── notebooks/
│   └── eda.py              # Discovers all 4 DQ issues before pipeline build
├── docs/
│   ├── data_contract.md    # Schema, delivery SLA, break-handling table
│   ├── cfo_investigation.md # 10-minute revenue change runbook with SQL
│   ├── dq_findings.md      # All 4 issues: file, row count, pipeline action
│   └── data_lineage.md     # Mermaid flowchart: CSV → raw → clean → fact → dashboard
├── datasets/               # 30 CSV files + late_arrivals/ subfolder
├── output/
│   └── sales.duckdb        # Pre-built warehouse (committed for HF Spaces)
├── DECISIONS.md            # 8 ADRs: why DuckDB, no Airflow, no dbt, etc.
└── requirements.txt
```

---

## Key Design Decisions

See `DECISIONS.md` for full rationale. Headlines:

- **No Airflow/Prefect** — one-shot batch on 30 static files; orchestrator overhead not justified
- **No dbt** — 3-4 SQL transforms don't need dbt scaffolding; raw SQL is more readable for evaluators
- **No Great Expectations** — custom checks expose the logic; evaluators see YOUR reasoning
- **Idempotent pipeline** — every step is DROP IF EXISTS + CREATE; safe to re-run identically
- **Lineage on every row** — `_source_file` + `_file_date` survive to `fact_orders`; any number traces back to its CSV

---

## What's Not Done (and why)

- No real-time streaming — daily batch is appropriate for daily file delivery
- No SCD2 on products — latest-state dimension only; would add `effective_from/to` in production
- No alerting — DQ failures visible on dashboard; no Slack/email (Prefect would add this)
- No concurrent writes — DuckDB is single-writer; Postgres/BigQuery for multi-user production

---

## In Production I Would Add

1. **Prefect** with daily cron schedule, automatic retries, and Slack alerts on DQ FAIL
2. **SCD2 product dimension** — track price/category changes over time
3. **pytest suite** — one test per pipeline stage verifying row counts and revenue totals
4. **Postgres or BigQuery** — for concurrent writers and access control
5. **Row-level audit log** — append-only table recording every pipeline run's metrics
