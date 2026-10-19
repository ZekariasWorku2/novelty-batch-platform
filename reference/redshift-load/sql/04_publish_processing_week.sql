BEGIN;

DELETE FROM product_trends.trend_features
WHERE as_of_week_end_date = DATE '<PROCESSING_WEEK_END>';

INSERT INTO product_trends.trend_features
SELECT *
FROM product_trends.trend_features_load
WHERE as_of_week_end_date = DATE '<PROCESSING_WEEK_END>';

END;
