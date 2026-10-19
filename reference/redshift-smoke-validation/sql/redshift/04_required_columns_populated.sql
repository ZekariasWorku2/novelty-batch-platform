SELECT COUNT(*) AS failure_count
FROM {{REDSHIFT_TABLE}}
WHERE as_of_week_end_date = DATE '{{PROCESSING_WEEK_END}}'
  AND (
    StockItemID IS NULL
    OR as_of_week_end_date IS NULL
    OR weeks_since_launch IS NULL
    OR units_sold_week IS NULL
    OR sales_amount_week IS NULL
  );