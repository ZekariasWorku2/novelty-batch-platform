SELECT COUNT(*) AS failure_count
FROM reference_new_product_trend.staged_trend_features_reference
WHERE units_sold_week < 0
   OR sales_amount_week < 0
   OR profit_week < -1000000
   OR profit_week > 1000000
   OR (is_trending_8wk IS NOT NULL AND is_trending_8wk NOT IN (0,1));