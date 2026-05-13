-- sql/dim_products.sql
-- Product dimension: one row per product_id (latest-state only, no SCD2).

DROP TABLE IF EXISTS dim_products;

CREATE TABLE dim_products AS
SELECT DISTINCT
    product_id,
    product_name,
    category
FROM fact_orders
ORDER BY product_id;
