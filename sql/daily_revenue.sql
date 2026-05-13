-- sql/daily_revenue.sql
-- Aggregated daily revenue view used by the dashboard.
-- Joins fact_orders with dim_dates for weekend flag.

DROP VIEW IF EXISTS daily_revenue;

CREATE VIEW daily_revenue AS
SELECT
    f.order_date,
    d.day_of_week,
    d.is_weekend,
    COUNT(*)                AS order_count,
    SUM(f.revenue)          AS total_revenue,
    AVG(f.revenue)          AS avg_order_value,
    COUNT(DISTINCT f.customer_id) AS unique_customers
FROM fact_orders f
JOIN dim_dates d USING (order_date)
GROUP BY f.order_date, d.day_of_week, d.is_weekend
ORDER BY f.order_date;
