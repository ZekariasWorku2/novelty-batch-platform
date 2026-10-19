SELECT
  COUNT(*) AS row_count,
  COALESCE(SUM(units_sold_week),0) AS units_total,
  COALESCE(SUM(sales_amount_week),0) AS sales_total,
  COALESCE(SUM(profit_week),0) AS profit_total
FROM {{REDSHIFT_TABLE}}
WHERE as_of_week_end_date = DATE '{{PROCESSING_WEEK_END}}';