# Architecture Decision Records — Case 7: Sales Pipeline

---

## ADR-001: Why Python + pandas for Ingestion (not Spark or Flink)

**Decision:** Use Python + glob + pandas to read CSV files.

**Rationale:** The workload is 30 static CSV files totaling ~19 MB. PySpark introduces JVM startup overhead and cluster configuration that is entirely disproportionate to this scale. Pandas reads all 30 files in under 10 seconds on any laptop. The code is also more readable for evaluators.

**In production:** If daily file volume exceeded ~1 GB per day or required real-time streaming, I'd switch to PySpark on Databricks or Apache Flink.

---

## ADR-002: Why NOT Airflow / Prefect / Dagster

**Decision:** Use a single `run_pipeline.py` script with sequential function calls instead of a workflow orchestrator.

**Rationale:** The pipeline processes 30 static CSV files in a one-shot batch run. Orchestrator overhead (server process, DAG definitions, scheduler daemon, web UI) is not justified for this workload. Each pipeline step is an idempotent Python function with structured logging — that's all the "orchestration" this workload needs.

**In production:** With daily arriving files, I'd use Prefect with scheduled flows, automatic retries on transient failures, Slack alerts on DQ FAIL, and a run history dashboard. The migration would be straightforward since each function in `run_pipeline.py` maps cleanly to a Prefect task.

---

## ADR-003: Why DuckDB (not Postgres or BigQuery)

**Decision:** Use DuckDB as the embedded analytical warehouse.

**Rationale:** DuckDB is zero-config, embeds in the Python process, reads CSVs natively, and supports the full SQL analytics dialect (window functions, QUALIFY, date_trunc, etc.). For a local pipeline producing a single `.duckdb` file, it eliminates all infrastructure setup. The dashboard reads from the same file.

**Tradeoffs acknowledged:**
- DuckDB is single-writer — concurrent pipeline runs would corrupt the database. In production with multiple writers, use Postgres or BigQuery.
- The `.duckdb` file must be committed to the repo for the HF Spaces dashboard to read it (no live pipeline on HF). This is acceptable for a demonstration.

**In production:** BigQuery (GCP) or Snowflake for multi-user access, concurrent writes, and built-in access control.

---

## ADR-004: Why NOT dbt

**Decision:** Write raw SQL files in `sql/` loaded directly by Python instead of using dbt.

**Rationale:** dbt adds project scaffolding (profiles.yml, dbt_project.yml, models/ directory, macros/, tests/) that is disproportionate for 3-4 SQL transforms. Raw SQL in `sql/*.sql` loaded by Python achieves identical results with less abstraction — and evaluators can read the SQL directly without understanding dbt conventions.

**In production:** With 50+ models, dbt's lineage tracking, automated testing (schema tests, custom tests), documentation generation, and incremental model support would be well worth the setup cost.

---

## ADR-005: Why Custom DQ Checks (not Great Expectations or Soda)

**Decision:** Write 5 hand-coded DQ check functions in `pipeline/quality_checks.py`.

**Rationale:** Great Expectations introduces a Checkpoint/Suite/DataContext abstraction layer that obscures the actual validation logic. For 4-5 known checks on a fixed schema, a plain Python function that runs a SQL query and returns a structured result is more transparent, more debuggable, and demonstrates the engineer's own reasoning about data quality.

**In production:** With 100+ assertions across dozens of tables, Great Expectations or Soda's declarative configuration and built-in alerting integrations would be worth the learning curve.

---

## ADR-006: Idempotency — Pipeline is Safe to Re-Run

**Decision:** Every CREATE TABLE statement is preceded by DROP TABLE IF EXISTS.

**Rationale:** If the pipeline is run twice (e.g., after a data fix or file re-delivery), it must produce the same output — not double-count rows. Dropping and recreating tables on each run guarantees this. The tradeoff is slightly longer runtime on re-runs (acceptable for a batch pipeline).

**Implementation:** See `pipeline/ingest.py`, `pipeline/transform.py` — every table creation is wrapped in DROP IF EXISTS.

---

## ADR-007: Lineage Metadata on Every Row

**Decision:** Add `_source_file` and `_load_timestamp` columns to every row during ingestion.

**Rationale:** These columns make it possible to answer "which file did this order come from?" and "when was it loaded?" — essential for the CFO's 10-minute investigation runbook. `_source_file` flows from `raw_orders` through to `fact_orders`, so any row in the dashboard can be traced back to its source CSV.

---

## ADR-008: Late Arrivals Handled as First-Class Input

**Decision:** The ingestion step scans both `datasets/` AND `datasets/late_arrivals/` for CSV files.

**Rationale:** The brief explicitly calls out a late file as an intentional DQ issue. Scanning only the main directory would silently miss it. By scanning both locations, the pipeline handles late delivery transparently — the late file's rows are tagged with their actual `_file_date` and processed identically to on-time files.
