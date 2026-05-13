# Data Lineage

## Pipeline Flow

```mermaid
flowchart LR
    A["📁 datasets/\nsales_*.csv\n(30 files)"] --> C
    B["📁 datasets/late_arrivals/\nsales_*.csv\n(late files)"] --> C

    C["🐍 ingest.py\n+ lineage metadata\n(_source_file, _load_timestamp, _file_date)"]
    C --> D["🗄️ raw_orders\n(DuckDB)\nAll rows, unmodified"]

    D --> E["✅ quality_checks.py\n5 DQ checks"]
    E --> F["📋 dq_results\n(DuckDB)\nPASS / WARN / FAIL per check"]

    D --> G["🐍 transform.py\nDeduplication"]
    G --> H["🗄️ clean_orders\n(DuckDB)\nDeduped on order_id"]

    H --> I{Null check}
    I -- "critical column IS NULL" --> J["🗄️ quarantine_orders\n(DuckDB)\nExcluded from revenue"]
    I -- "all critical fields present" --> K["🗄️ fact_orders\n(DuckDB)\nWith calculated revenue"]

    K --> L["🗄️ dim_products"]
    K --> M["🗄️ dim_dates"]
    K --> N["📊 daily_revenue VIEW"]

    N --> O["🖥️ Streamlit Dashboard\nTab 1: Revenue Overview\nTab 2: Products\nTab 3: DQ Status"]
    F --> O
    J --> O
```

## Table Descriptions

| Table | Layer | Description |
|-------|-------|-------------|
| `raw_orders` | Raw | All ingested rows. Every source file row lands here. |
| `dq_results` | Meta | Output of 5 DQ checks. Dashboard reads this for DQ tab. |
| `clean_orders` | Clean | Deduplicated: one row per `order_id` (latest load wins). |
| `quarantine_orders` | Quarantine | Rows with nulls in critical fields, excluded from revenue. |
| `fact_orders` | Modeled | Clean rows with calculated `revenue`. Source of truth. |
| `dim_products` | Dimension | One row per product (latest state). |
| `dim_dates` | Dimension | One row per date with calendar attributes. |
| `daily_revenue` | View | Aggregated revenue per day. Dashboard's primary data source. |

## Lineage Columns

Every row in `fact_orders` retains:
- `_source_file` — which CSV file it came from (e.g., `sales_2025-03-01.csv`)
- `_file_date` — the date that file represents

This enables the CFO investigation runbook: any revenue number can be traced back to a specific source file.
