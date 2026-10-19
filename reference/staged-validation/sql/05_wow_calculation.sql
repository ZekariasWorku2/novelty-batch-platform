WITH x AS (
  SELECT *,
    LAG(units_sold_week) OVER (PARTITION BY StockItemID ORDER BY as_of_week_end_date) AS expected_prev_units,
    LAG(sales_amount_week) OVER (PARTITION BY StockItemID ORDER BY as_of_week_end_date) AS expected_prev_sales
  FROM reference_new_product_trend.staged_trend_features_reference
), y AS (
  SELECT *,
    CASE WHEN expected_prev_units IS NULL OR expected_prev_units = 0 THEN NULL
         ELSE (CAST(units_sold_week AS DOUBLE) - expected_prev_units) / expected_prev_units
    END AS expected_growth
  FROM x
)
SELECT COUNT(*) AS failure_count
FROM y
WHERE prev_week_units IS DISTINCT FROM expected_prev_units
   OR prev_week_sales IS DISTINCT FROM expected_prev_sales
   OR (
      wow_units_growth_rate IS DISTINCT FROM expected_growth
      AND NOT (
        wow_units_growth_rate IS NOT NULL
        AND expected_growth IS NOT NULL
        AND ABS(wow_units_growth_rate - expected_growth) <= 0.000001
      )
   );