WITH product_perf AS (
  SELECT StockItemID, launch_quarter, MAX(first_8wk_units) AS first_8wk_units
  FROM reference_new_product_trend.staged_trend_features_reference
  WHERE first_8wk_units IS NOT NULL
  GROUP BY StockItemID, launch_quarter
), cutoffs AS (
  SELECT launch_quarter,
         APPROX_PERCENTILE(CAST(first_8wk_units AS DOUBLE), 0.75) AS p75_cutoff
  FROM product_perf
  GROUP BY launch_quarter
), threshold AS (
  SELECT MAX(min_8week_units) AS min_8week_units
  FROM reference_new_product_trend.trend_thresholds_reference
  WHERE product_category = 'DEFAULT'
)
SELECT COUNT(*) AS failure_count
FROM reference_new_product_trend.staged_trend_features_reference s
JOIN cutoffs c ON s.launch_quarter = c.launch_quarter
CROSS JOIN threshold t
WHERE s.weeks_since_launch = 7
  AND s.is_trending_8wk IS NOT NULL
  AND s.is_trending_8wk <>
      CASE WHEN s.first_8wk_units >= c.p75_cutoff
             AND s.first_8wk_units >= t.min_8week_units
           THEN 1 ELSE 0 END;