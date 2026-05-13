-- sql/create_clean.sql
-- Deduplicates raw_orders on order_id.
-- When an order_id appears in multiple files (re-delivery), the row from the
-- latest _load_timestamp is kept (last-write-wins).

DROP TABLE IF EXISTS clean_orders;

CREATE TABLE clean_orders AS
SELECT *
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY _load_timestamp DESC
        ) AS _rn
    FROM raw_orders
    WHERE order_id IS NOT NULL
) ranked
WHERE _rn = 1;

-- Drop the helper column
ALTER TABLE clean_orders DROP COLUMN _rn;
