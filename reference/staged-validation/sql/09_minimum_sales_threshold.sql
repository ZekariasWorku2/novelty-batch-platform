WITH threshold AS (
  SELECT MAX(min_8week_units) AS min_8week_units
  FROM reference_new_product_trend.trend_thresholds_reference
  WHERE product_category = 'DEFAULT'
)
SELECT COUNT(*) AS failure_count
FROM reference_new_product_trend.staged_trend_features_reference s
CROSS JOIN threshold t
WHERE s.is_trending_8wk = 1
  AND s.first_8wk_units < t.min_8week_units;