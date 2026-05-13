-- sql/dim_products.sql
-- Product dimension: one row per product_id (latest-state only, no SCD2).
-- Uses FIRST non-null product_name to handle the March 26 null spike where
-- some rows have a valid product_id but null product_name.

DROP TABLE IF EXISTS dim_products;

CREATE TABLE dim_products AS
SELECT
    product_id,
    -- Pick the first non-null product_name for each product_id
    MAX(product_name)  AS product_name,
    MAX(category)      AS category
FROM fact_orders
WHERE product_id IS NOT NULL
GROUP BY product_id
ORDER BY product_id;
