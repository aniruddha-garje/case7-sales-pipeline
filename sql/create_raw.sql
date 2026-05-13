-- sql/create_raw.sql
-- DDL for the raw_orders table.
-- This table holds all ingested rows before any cleaning or deduplication.
-- Metadata columns (_source_file, _load_timestamp, _file_date) enable lineage tracking.

DROP TABLE IF EXISTS raw_orders;

CREATE TABLE raw_orders (
    order_id          VARCHAR,
    order_timestamp   VARCHAR,        -- kept as string; cast to TIMESTAMP in fact_orders
    customer_id       VARCHAR,
    product_id        VARCHAR,
    product_name      VARCHAR,
    category          VARCHAR,
    qty               INTEGER,
    unit_price        DOUBLE,
    discount_pct      DOUBLE,
    region            VARCHAR,
    -- Lineage metadata
    _source_file      VARCHAR,        -- filename, e.g. sales_2025-03-01.csv
    _load_timestamp   TIMESTAMP,      -- when the row was loaded into DuckDB
    _file_date        DATE            -- date extracted from filename
);
