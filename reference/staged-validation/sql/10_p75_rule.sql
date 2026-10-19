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
)
SELECT COUNT(*) AS failure_count
FROM reference_new_product_trend.staged_trend_features_reference s
JOIN cutoffs c ON s.launch_quarter = c.launch_quarter
WHERE s.is_trending_8wk = 1
  AND s.first_8wk_units < c.p75_cutoff;