# Case 7: Streaming Sales Pipeline — From CSV Chaos to a Trusted Dashboard

> **Live Dashboard:** [TODO: Add Hugging Face Spaces URL after deployment]

An e-commerce startup drops daily sales CSVs into a shared folder. Different teams report different revenue numbers. This pipeline produces **one trusted number**, proves it's trustworthy, and gives the CFO a dashboard she can rely on.

---

## Problem Statement

- 30 daily CSV files for March 2025 (~5,000–10,000 rows/day, ~19 MB total)
- 4 intentional data-quality issues: duplication, missing/late files, schema drift, null spikes
- Goal: clean, deduplicated fact table + live dashboard with DQ status

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

## How to Run Locally

### 1. Clone the repo
```bash
git clone <repo-url>
cd case7-sales-pipeline
```

### 2. Set up Python environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run the pipeline
```bash
python pipeline/run_pipeline.py
```

This generates `output/sales.duckdb` with all cleaned tables.

### 4. Launch the dashboard
```bash
streamlit run dashboard/app.py
```

---

## Project Structure

```
case7-sales-pipeline/
├── pipeline/           # Ingestion, DQ checks, transforms, orchestration
├── dashboard/          # Streamlit app
├── sql/                # All SQL DDL and transform queries
├── docs/               # Data contract, CFO runbook, DQ findings, lineage
├── notebooks/          # EDA script
├── datasets/           # Raw CSV files (30 days + late_arrivals/)
├── output/             # Generated DuckDB warehouse (gitignored)
└── deck/               # Presentation slides
```

---

## The 4 DQ Issues Found

See `docs/dq_findings.md` for the full write-up. Summary:

1. **Duplication** — Duplicate `order_id` values across files; pipeline deduplicates on latest load
2. **Missing/Late File** — One date's file arrived late in `late_arrivals/`; pipeline scans both directories
3. **Schema Drift** — One file has a different column name; pipeline normalizes before loading
4. **Null Spike** — One file has abnormally high nulls in a critical column; affected rows quarantined

---

## Key Design Decisions

See `DECISIONS.md` for full rationale. In brief:
- No Airflow/Prefect — one-shot batch on 30 static files doesn't justify orchestrator overhead
- No dbt — 3-4 transforms don't justify dbt scaffolding; raw SQL is more readable for evaluators
- No Great Expectations — custom DQ checks expose the logic clearly
- Idempotent pipeline — safe to re-run; DROP TABLE IF EXISTS before every CREATE

---

## What's Not Done (and why)

- No real-time streaming — batch is appropriate for daily file delivery
- No SCD2 on products — latest-state only; would add in production
- No alerting — DQ failures shown on dashboard but no Slack/email notifications
- No concurrent writes — DuckDB is single-writer; Postgres/BigQuery for multi-user production

---

## In Production I Would Add

- Prefect with daily cron schedule + retry logic
- Slack alerts on DQ FAIL
- SCD2 product dimension
- Row-level data lineage to source system
- Automated tests (pytest) for each pipeline stage
