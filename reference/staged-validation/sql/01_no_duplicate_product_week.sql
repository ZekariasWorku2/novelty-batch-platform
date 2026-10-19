SELECT COUNT(*) AS failure_count
FROM (
  SELECT StockItemID, as_of_week_end_date, COUNT(*) AS cnt
  FROM reference_new_product_trend.staged_trend_features_reference
  GROUP BY StockItemID, as_of_week_end_date
  HAVING COUNT(*) > 1
) d;