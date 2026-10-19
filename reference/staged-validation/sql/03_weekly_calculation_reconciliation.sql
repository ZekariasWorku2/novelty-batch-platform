WITH raw_weekly AS (
  SELECT
    l.stock_item_id,
    DATE_ADD('day', 6, DATE_ADD('day', -(DAY_OF_WEEK(i.invoice_date) % 7), i.invoice_date)) AS week_end,
    SUM(l.quantity) AS expected_units,
    SUM(l.quantity * l.unit_price) AS expected_sales,
    SUM(l.line_profit) AS expected_profit
  FROM reference_new_product_trend.raw_invoice_lines_reference l
  JOIN reference_new_product_trend.raw_invoices_reference i
    ON l.invoice_id = i.invoice_id
  WHERE l.quantity > 0
    AND COALESCE(i.is_credit_note, false) = false
  GROUP BY l.stock_item_id,
           DATE_ADD('day', 6, DATE_ADD('day', -(DAY_OF_WEEK(i.invoice_date) % 7), i.invoice_date))
)
SELECT COUNT(*) AS failure_count
FROM reference_new_product_trend.staged_trend_features_reference s
LEFT JOIN raw_weekly r
  ON s.StockItemID = r.stock_item_id
 AND s.as_of_week_end_date = r.week_end
WHERE COALESCE(s.units_sold_week,0) <> COALESCE(r.expected_units,0)
   OR ABS(COALESCE(s.sales_amount_week,0) - COALESCE(r.expected_sales,0)) > 0.01
   OR ABS(COALESCE(s.profit_week,0) - COALESCE(r.expected_profit,0)) > 0.01;