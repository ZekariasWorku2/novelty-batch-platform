# Architecture, data flow and source contracts

Account from AWS inspection: `672350744457`, region `us-east-1`.
Lake bucket: `novelty-margin-lakehouse-672350744457`.

## Orchestration

The recovered DAG is `airflow/dags/new_product_trend_weekly.py`.
Task order: start -> determine_processing_window ->
extract_source_to_raw_s3 -> validate_raw_data -> transform_to_staging ->
validate_staged_data -> promote_validated_to_curated ->
publish_curated_to_redshift -> post_load_smoke_validation ->
record_pipeline_audit -> end.

Every Sunday at 02:00 America/New_York, the processing window is Sunday
inclusive to next Sunday exclusive. The DAG is paused on first creation.

## Ingestion contract

`reference/raw-ingest/scripts/raw_ingest.py` connects to SQL Server via JDBC
using a secret ARN (username/password stored in Secrets Manager).
`reference/raw-ingest/config/source_tables.json` is a **proposed** SQL Server
schema contract. It extracts weekly invoice records and full dimension
snapshots to:

`raw/wwi/{table}/week_start=YYYY-MM-DD/part-*.csv.gz`

Each run creates the exact manifest at the key passed by the DAG. Its fields:
`run_id`, `processing_week_start`,
`processing_week_end_exclusive`, `tables[table].expected_files`,
`source_row_count`, `source_schema` and `daily_counts`.
The recovered raw validator verifies these against physical S3 data.

## Transformation

`reference/transform/scripts/transform_to_staging.py` reads accumulated
history. Launch date uses **earliest observed sale**, not product master-data
creation date, until a source-of-truth launch date is supplied.
Excludes credit notes and nonpositive quantity. Creates a row for each
product's first eight Sunday-to-Saturday sales weeks (zero-fills missing).
Provides weekly units/sales/profit, cumulative metrics, preceding-week values,
week-over-week units growth, customer-count proxy and product attributes.

The `first_8wk_*` aggregates and `is_trending_8wk` label are null until
week 7 closes; the label uses the launch-quarter completed-cohort 75th
percentile and a configured minimum-units threshold. This is for descriptive
eight-week outcomes, not a point-in-time ML feature dataset. For historical
ML training, materialize label as a distinct future target and recompute
cohort thresholds using only what would have been known at the feature
timestamp to avoid leakage.

Staging: `staging/new_product_trend/features/as_of_year=YYYY/as_of_month=MM/`
Curated: `curated/new_product_trend/features/as_of_year=YYYY/as_of_month=MM/`.
The recovered promotion script copies only after validation.

## Validation and publish

Recovered raw validator: files, schema, counts, date coverage, null critical
keys and historical-count checks.

Recovered staged validator: Spark schema/readability, DQDL, 12 Athena SQL
queries. The AWS reference Athena raw tables point to **older landing files**.
Before an end-to-end run, update raw Athena catalog pointers/partitions to the
ingestion output and register staged partitions to prevent false reconciliation
failure. This integration is documented but untested.

Recovered Redshift controller: staging COPY + publication of the processing
week. Recovered smoke validator: row-count, duplicates, nulls, totals, expected
week and queryability. A Serverless workgroup/namespace must be created and
service eligibility confirmed first.

## Standalone Step Functions

The four recovered reference Step Functions definitions in `stepfunctions/`
are optional testing gates; the primary weekly flow is MWAA, not Step Functions.
The historic billing-credit guardrail belongs outside this pipeline repo.
