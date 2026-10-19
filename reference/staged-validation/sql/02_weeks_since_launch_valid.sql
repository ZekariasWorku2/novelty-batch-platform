SELECT COUNT(*) AS failure_count
FROM reference_new_product_trend.staged_trend_features_reference
WHERE weeks_since_launch < 0
   OR weeks_since_launch > 7
   OR weeks_since_launch <> FLOOR(DATE_DIFF('day', launch_date, as_of_week_end_date) / 7.0);