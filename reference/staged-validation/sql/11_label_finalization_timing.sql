SELECT COUNT(*) AS failure_count
FROM reference_new_product_trend.staged_trend_features_reference
WHERE weeks_since_launch < 7
  AND is_trending_8wk IS NOT NULL;