# Data Contract — Daily Sales CSV

> **Status:** Draft — to be finalized after EDA confirms schema and DQ thresholds.

## Source
E-commerce order system, delivered as daily CSV files by the upstream order-processing team.

## Delivery
- One file per day: `sales_YYYY-MM-DD.csv`
- Delivered to `datasets/` by midnight UTC
- Late files may appear in `datasets/late_arrivals/` subfolder
- File naming convention is strict: any deviation will cause the file to be skipped

## Schema

| Column | Type | Nullable | Constraints |
|--------|------|----------|-------------|
| order_id | STRING | No | Unique across all files; format ORD#### |
| order_timestamp | ISO 8601 STRING | No | Must fall within the file's date |
| customer_id | STRING | No | Format: C##### |
| product_id | STRING | No | Must exist in the product catalog |
| product_name | STRING | No | |
| category | STRING | No | One of: Electronics, Apparel, Grocery, Stationery, Home & Kitchen |
| qty | INTEGER | No | 1–10 |
| unit_price | FLOAT | No | > 0 |
| discount_pct | FLOAT | No | 0.0 to 0.50 |
| region | STRING | No | One of: North, South, East, West |

## Quality Expectations

| Metric | Threshold |
|--------|-----------|
| Row count per file | 5,000–10,000 |
| Null rate (any column) | < 1% |
| Duplicate order_ids | 0 within a file, 0 across files |
| Schema | Columns must match exactly: name, order, count |
| File delivery | Every calendar date must have exactly one file |

## When the Contract Breaks

| Violation | Pipeline Behavior |
|-----------|------------------|
| Missing file for a date | Log WARNING, continue, flag on dashboard DQ tab |
| File in late_arrivals/ | Load normally, tag with _source_file for traceability |
| Schema mismatch (unknown column names) | Attempt column normalization; if impossible, REJECT file, log ERROR |
| Duplicate order_ids | Deduplicate (keep latest _load_timestamp), log WARNING |
| Null spike (> 5% in any critical column) | Load but QUARANTINE null rows to quarantine_orders, log WARNING |
| Row count outside 5k–10k range | Log WARNING, load anyway, flag on dashboard |

## Derived Fields (Calculated by Pipeline)

```
revenue = qty * unit_price * (1 - discount_pct)
```

This is NOT provided in the source CSV — it is calculated in `sql/fact_orders.sql`.

## Contact
Data owner: upstream order-processing team (TBD)
Pipeline owner: Aniruddha Garje
