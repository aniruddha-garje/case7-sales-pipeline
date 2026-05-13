-- sql/dim_dates.sql
-- Date dimension derived from fact_orders dates.

DROP TABLE IF EXISTS dim_dates;

CREATE TABLE dim_dates AS
SELECT DISTINCT
    order_date,
    EXTRACT(DOW  FROM order_date)::INTEGER  AS day_of_week,   -- 0=Sunday, 6=Saturday
    EXTRACT(DAY  FROM order_date)::INTEGER  AS day_of_month,
    CASE
        WHEN EXTRACT(DOW FROM order_date) IN (0, 6) THEN TRUE
        ELSE FALSE
    END                                     AS is_weekend
FROM fact_orders
ORDER BY order_date;
