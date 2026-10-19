REFERENCE: CURATED S3 -> REDSHIFT SERVERLESS PUBLISH STEP

Purpose
-------
Production-style reference implementation only. There is no schedule or automatic trigger.

Runtime flow
------------
Step Functions
  -> Glue Python Shell controller
  -> Redshift Data API
  -> CREATE schema/tables if needed
  -> TRUNCATE staging table
  -> Redshift COPY curated Parquet from S3
  -> replace the requested processing week in the final mart
  -> write load audit to S3
  -> start existing post-load smoke-validation Glue job

Target objects
--------------
Database: analytics
Schema: product_trends
Stage table: product_trends.trend_features_load
Final table: product_trends.trend_features
Workgroup: reference-new-product-trend-wg
Redshift S3 role: arn:aws:iam::672350744457:role/ReferenceRedshiftCuratedLoadRole

IMPORTANT
---------
This setup has no schedule and has not been executed.
The Redshift Serverless namespace/workgroup must exist before execution.
The account currently requires Redshift service subscription/opt-in.
