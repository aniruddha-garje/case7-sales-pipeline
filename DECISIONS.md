# Decisions Log — Case 7: Streaming Sales Pipeline

---

## Assumptions I made

1. **"30 daily files" means one file per calendar day, not 30 business days** — because the brief says "March 2025" and March has 31 days; a gap means a missing delivery, not a weekend skip.
2. **`order_id` is the correct dedup key** — the brief defines it as unique per order; a re-delivered file means the same orders are re-sent with identical IDs.
3. **Rows with null `unit_price` should be quarantined, not dropped silently** — revenue = qty × unit_price × (1 − discount_pct); a null price makes the row uncountable, but the order itself is real and should be visible on the DQ dashboard.
4. **The late-arrivals folder is a permanent delivery pattern, not a one-off** — so the ingestion step scans it on every run rather than handling it as a special case.
5. **"Trusted number" means reproducible and auditable** — the same pipeline run on the same data must always produce the same result (idempotency), and every row must trace back to its source file.
6. **Evaluators will read the code** — so clarity of logic is weighted above brevity; I chose explicit SQL and named functions over clever one-liners.

---

## Trade-offs

| Choice | Alternative | Why I picked this |
|--------|-------------|-------------------|
| DuckDB (embedded) | Postgres / BigQuery | Zero config, single file, full SQL dialect, reads CSVs natively — perfect for a local pipeline with a single writer. In production with concurrent users I'd use BigQuery. |
| Custom DQ checks | Great Expectations / Soda | My 5-function approach is readable and directly evaluable; GE's Checkpoint/Suite abstraction adds setup cost for 4-5 known checks without meaningful upside at this scale. |
| Plain `run_pipeline.py` | Airflow / Prefect / Dagster | One-shot batch on 30 static files; orchestrator overhead (server, scheduler, DAG definitions) is not justified. Each function already has structured logging and returns a typed result dict. |
| Raw SQL in `sql/` | dbt | 3-4 transforms don't need dbt's project scaffolding (profiles.yml, dbt_project.yml, macros/). Raw SQL is self-documenting and evaluator-friendly. With 50+ models I'd use dbt. |
| Streamlit + Plotly | React + D3 / Dash | Built 3 functional, visually polished tabs in hours; HF Spaces hosts it for free; no frontend build tooling needed. |
| DROP + CREATE (full refresh) | Incremental / merge | Guarantees idempotency on a 30-file dataset where full refresh takes ~3 seconds. At scale I'd switch to incremental loads to keep runtime flat. |
| Commit `sales.duckdb` to repo | Run pipeline on HF | HF Spaces free tier has no persistent storage and no scheduled jobs. Committing the pre-built DB is the standard HF Spaces pattern for read-only dashboards. |

---

## What I de-scoped and why

- **Real-time / streaming ingestion** — daily file delivery is a daily batch problem; adding Kafka or Flink would be engineering theatre at this scale.
- **SCD2 on the product dimension** — the dataset has no product changes across the 30 files; latest-state is correct for March 2025. I'd add `effective_from` / `effective_to` in a production system that tracks price history.
- **pytest suite** — pipeline correctness is verified by row-count and revenue assertions printed in `run_pipeline.py`; a formal test suite was de-scoped in favour of building the full end-to-end pipeline and dashboard within the time box.
- **Alerting (Slack / email)** — DQ failures surface on the dashboard's DQ Audit tab with severity badges. Notification routing (Prefect + Slack webhook) would be the first production addition.
- **Column-level access control** — `customer_id` is present in the fact table without masking. Production would apply row-level security and mask PII before dashboard exposure.

---

## What I'd do differently with another day

- **Add pytest from the start** — the absence of a test suite made late-stage refactoring (connection pattern, column escaping) riskier than it needed to be. I'd write one assertion test per pipeline stage before writing the transformation logic.
- **Design the DB path for deployment early** — the `output/sales.duckdb` vs `dashboard/output/sales.duckdb` issue only surfaced at HF deployment time. A single canonical path agreed on at the start would have avoided the late copy-and-commit.
- **Use `st.html()` from the beginning for all custom tables** — I started with `st.markdown(unsafe_allow_html=True)` and hit the Markdown code-block escaping issue. `st.html()` is the correct primitive for injecting raw HTML into Streamlit and should be the default choice.
- **Pre-compute DQ metrics into the warehouse** — the dashboard currently re-runs null-rate SQL on every page load. Materialising these into a `dq_metrics` table at pipeline time would make the dashboard faster and the queries simpler.
