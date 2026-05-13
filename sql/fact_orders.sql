-- sql/fact_orders.sql
-- Builds the fact_orders table from clean_orders.
-- Excludes quarantined rows (null critical fields).
-- Calculates revenue = qty * unit_price * (1 - discount_pct).

DROP TABLE IF EXISTS fact_orders;

CREATE TABLE fact_orders AS
SELECT
    order_id,
    CAST(order_timestamp AS TIMESTAMP)                              AS order_timestamp,
    DATE_TRUNC('day', CAST(order_timestamp AS TIMESTAMP))::DATE     AS order_date,
    customer_id,
    product_id,
    product_name,
    category,
    qty,
    unit_price,
    discount_pct,
    region,
    ROUND(qty * unit_price * (1 - discount_pct), 2)                AS revenue,
    _source_file,
    _file_date
FROM clean_orders
WHERE order_id     IS NOT NULL
  AND qty          IS NOT NULL
  AND unit_price   IS NOT NULL
  AND discount_pct IS NOT NULL;
