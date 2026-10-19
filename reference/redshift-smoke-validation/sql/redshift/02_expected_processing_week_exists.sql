SELECT COUNT(*) AS row_count
FROM {{REDSHIFT_TABLE}}
WHERE as_of_week_end_date = DATE '{{PROCESSING_WEEK_END}}';