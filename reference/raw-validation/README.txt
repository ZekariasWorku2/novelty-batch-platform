RAW DATA VALIDATION REFERENCE STEP

Purpose
This is an idle reference implementation of the raw-data validation gate discussed for the weekly data-engineering pipeline. Nothing is scheduled and the Glue job is not running.

Services used
1. Amazon S3
   - Stores the Glue validation script, configuration, example ingestion manifest, audit results, and the raw files being validated.
2. AWS Glue
   - A PySpark job reads the landed raw files and performs the actual checks.
3. AWS Step Functions
   - Orchestrates the validation as a gate. If the Glue job succeeds, the workflow moves to RawValidationPassed. If it fails, the workflow sends an alert and fails.
4. Amazon SNS
   - Receives the failure notification.
5. AWS IAM
   - Provides separate least-privilege-style roles for Glue and Step Functions.

How source-to-raw reconciliation works
The ingestion step writes an ingestion manifest after extracting from SQL Server. The manifest records:
- expected S3 file keys
- source row count
- source schema
- per-day source counts for the weekly processing window

The Glue validation job compares the persisted raw S3 files against that manifest.

Checks implemented
- expected raw files exist
- raw files are readable
- no unexpected/duplicate physical file copies
- source and raw row counts reconcile
- raw row count is not zero
- current row count is compared with recent weekly validation history
- Sunday-to-Saturday processing-window counts reconcile
- required source columns exist
- landed data types match the source schema captured at extraction
- critical source keys are not NULL

PASS/FAIL behavior
Glue validation succeeds -> Step Functions moves to RawValidationPassed.
Glue validation raises an error -> Step Functions publishes to SNS and enters RawValidationFailed.

Important
This is a reference setup only. There is no EventBridge schedule, no automatic trigger, and no Glue execution has been started.
