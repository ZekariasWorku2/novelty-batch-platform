WITH raw_totals AS (
  SELECT
    SUM(l.quantity) AS units_total,
    SUM(l.quantity * l.unit_price) AS sales_total,
    SUM(l.line_profit) AS profit_total
  FROM reference_new_product_trend.raw_invoice_lines_reference l
  JOIN reference_new_product_trend.raw_invoices_reference i
    ON l.invoice_id = i.invoice_id
  WHERE l.quantity > 0
    AND COALESCE(i.is_credit_note, false) = false
), staged_totals AS (
  SELECT
    SUM(units_sold_week) AS units_total,
    SUM(sales_amount_week) AS sales_total,
    SUM(profit_week) AS profit_total
  FROM reference_new_product_trend.staged_trend_features_reference
)
SELECT CASE
  WHEN r.units_total = s.units_total
   AND ABS(r.sales_total - s.sales_total) <= 0.01
   AND ABS(r.profit_total - s.profit_total) <= 0.01
  THEN 0 ELSE 1 END AS failure_count
FROM raw_totals r CROSS JOIN staged_totals s;