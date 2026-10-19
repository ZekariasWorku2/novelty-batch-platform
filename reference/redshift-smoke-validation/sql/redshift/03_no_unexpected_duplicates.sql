SELECT COUNT(*) AS failure_count
FROM (
  SELECT StockItemID, as_of_week_end_date, COUNT(*) AS cnt
  FROM {{REDSHIFT_TABLE}}
  WHERE as_of_week_end_date = DATE '{{PROCESSING_WEEK_END}}'
  GROUP BY StockItemID, as_of_week_end_date
  HAVING COUNT(*) > 1
) d;