WITH x AS (
  SELECT *,
    SUM(units_sold_week) OVER (
      PARTITION BY StockItemID ORDER BY as_of_week_end_date
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS expected_cumulative_units,
    SUM(sales_amount_week) OVER (
      PARTITION BY StockItemID ORDER BY as_of_week_end_date
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS expected_cumulative_sales
  FROM reference_new_product_trend.staged_trend_features_reference
)
SELECT COUNT(*) AS failure_count
FROM x
WHERE cumulative_units_to_date <> expected_cumulative_units
   OR ABS(cumulative_sales_to_date - expected_cumulative_sales) > 0.01;