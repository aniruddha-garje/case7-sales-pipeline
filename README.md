# Case 7: Streaming Sales Pipeline — From CSV Chaos to a Trusted Dashboard

**Live demo:** https://huggingface.co/spaces/AniruddhaGarje/case7-sales-dashboard
**Repo:** https://github.com/aniruddha-garje/case7-sales-pipeline
**Demo video:** _(add Loom link)_

---

## What this is

An e-commerce startup was getting different revenue numbers from every team because each team counted CSVs differently — duplicates, late files, null prices, and schema changes were all silently corrupting results. This pipeline ingests 30 daily sales CSVs for March 2025, detects and resolves all 4 data-quality issues automatically, and delivers a single auditable revenue number with a CFO-facing dashboard that shows exactly what was fixed and why.

---

## Verified pipeline output

| Metric | Value |
|--------|-------|
| Total Revenue (March 2025) | **Rs. 10,276,245.96** |
| Total Orders (after dedup + quarantine) | **205,903** |
| Unique Customers | **49,173** |
| Avg Order Value | **Rs. 49.91** |
| Raw rows ingested | 214,300 |
| Duplicates removed | 6,152 |
| Rows quarantined (null `unit_price`) | 2,245 |
| DQ issues detected | **4 / 4** |

---

## How to run locally

```bash
# 1. Clone
git clone https://github.com/aniruddha-garje/case7-sales-pipeline.git
cd case7-sales-pipeline

# 2. Install dependencies
python -m venv venv
venv\Scripts\activate        # Windows — use source venv/bin/activate on Mac/Linux
pip install -r requirements.txt

# 3. Run the full pipeline  (ingest → DQ checks → transform → warehouse)
python pipeline/run_pipeline.py

# 4. Launch the dashboard
streamlit run dashboard/app.py
# → opens at http://localhost:8501
```

The pipeline is **idempotent** — safe to re-run any number of times; always produces the same output.

---

## Stack

| Layer | Tool | Why |
|-------|------|-----|
| Ingestion | Python + glob + pandas | 30 static CSVs don't need an orchestrator — plain functions are more readable and debuggable |
| DQ Checks | Custom Python (5 checks) | Evaluators see my logic, not a library's abstraction; straightforward to extend |
| Warehouse | DuckDB (embedded) | Zero config, full SQL analytics dialect, reads CSVs natively, single `.duckdb` file for HF Spaces |
| Transforms | Raw SQL via DuckDB | 3-4 transforms don't justify dbt scaffolding; SQL is self-documenting |
| Dashboard | Streamlit + Plotly | Free HF Spaces deployment, 3 functional tabs built without frontend overhead |
| Deployment | Hugging Face Spaces (Docker) | Free tier; pre-built `.duckdb` committed to repo — no live pipeline needed on HF |

---

## The 4 DQ issues found and fixed

| # | Type | File | Impact | Fix |
|---|------|------|--------|-----|
| 1 | **Duplication** | `sales_2025-03-15.csv` is a full re-send of March 14 | 6,152 excess rows; ~Rs. 300k revenue overcount | Dedup on `order_id`, keep latest `_load_timestamp` |
| 2 | **Late file** | `sales_2025-03-18.csv` landed in `late_arrivals/` subfolder, not main folder | Entire day silently missing from revenue | Ingestion scans both `datasets/` and `datasets/late_arrivals/` on every run |
| 3 | **Schema drift** | `sales_2025-03-22.csv` has `item_name` column + extra `channel` column | Breaks INSERT, corrupts downstream joins | Rename `item_name` → `product_name`, drop `channel` at ingest time |
| 4 | **Null spike** | `sales_2025-03-26.csv`: `unit_price` 35% null (2,245 rows) | Revenue calculation on null price → silent miscalculation | Quarantine null rows to `quarantine_orders`, exclude from `fact_orders` and all revenue metrics |

---

## Project structure

```
case7-sales-pipeline/
├── pipeline/
│   ├── ingest.py           # Scan both folders, normalize schema, tag lineage (_source_file, _file_date)
│   ├── quality_checks.py   # 5 DQ checks → structured results stored in dq_results table
│   ├── transform.py        # Dedup → quarantine → fact_orders → dim tables
│   └── run_pipeline.py     # Orchestration: ingest → check → transform → summary log
├── dashboard/
│   └── app.py              # 3 tabs: Revenue Performance / Product Intelligence / DQ Audit
├── docs/
│   ├── data_contract.md    # Schema, delivery SLA, break-handling per violation type
│   ├── cfo_investigation.md # 10-minute runbook: "why did Monday's revenue change by 3%?"
│   ├── dq_findings.md      # All 4 issues: discovery method, row count, pipeline action
│   └── data_lineage.md     # Mermaid diagram: CSV → raw → clean → fact → dashboard
├── datasets/               # 29 main-folder CSVs + late_arrivals/sales_2025-03-18.csv
├── output/
│   └── sales.duckdb        # Pre-built warehouse (committed so HF Spaces serves without a pipeline run)
└── requirements.txt
```

---

## What's NOT done

- **No real-time ingestion** — daily batch is the correct fit for daily file delivery; streaming adds latency management complexity with no benefit here
- **No SCD2 on products** — product dimension is latest-state only; `effective_from` / `effective_to` columns needed in production to track price history
- **No alerting** — DQ failures are visible on the dashboard but send no notifications; Prefect + Slack would cover this in production
- **No automated test suite** — pipeline correctness verified by row-count assertions in `run_pipeline.py`; a proper pytest suite is absent
- **No access control** — DuckDB is single-file, single-writer; correct for a demo, not for multi-user production

---

## In production I would also add

1. **Prefect orchestration** — daily scheduled flow with automatic retries on transient failures and Slack/email alerts on any DQ FAIL status
2. **pytest suite** — one test per pipeline stage: assert row counts, assert zero duplicates in `fact_orders`, assert revenue total matches a known snapshot
3. **SCD2 product dimension** — append-only with `effective_from` / `effective_to` to catch silent price and category changes over time
4. **Postgres or BigQuery** — replaces DuckDB for concurrent access, role-based access control, and column-level encryption on customer data
5. **Incremental loads** — replace full DROP + CREATE with `INSERT WHERE order_date > last_loaded_date` to keep runtime flat as data volume grows
