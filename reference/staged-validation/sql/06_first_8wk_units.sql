WITH expected AS (
  SELECT StockItemID,
         SUM(CASE WHEN weeks_since_launch BETWEEN 0 AND 7 THEN units_sold_week ELSE 0 END) AS expected_first_8wk_units
  FROM reference_new_product_trend.staged_trend_features_reference
  GROUP BY StockItemID
)
SELECT COUNT(*) AS failure_count
FROM reference_new_product_trend.staged_trend_features_reference s
JOIN expected e ON s.StockItemID = e.StockItemID
WHERE s.first_8wk_units IS NOT NULL
  AND s.first_8wk_units <> e.expected_first_8wk_units;