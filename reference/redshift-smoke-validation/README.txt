REDSHIFT POST-LOAD SMOKE VALIDATION - REFERENCE ARCHITECTURE

Idle reference implementation. No Redshift cluster/Serverless workgroup is created,
nothing is scheduled, and nothing has been executed.

FLOW
Upstream Redshift load result
  -> Step Functions checks load_status == SUCCEEDED
  -> Glue Python Shell job: reference-redshift-postload-smoke-validation
     -> Athena calculates expected metrics from trusted curated S3
     -> Redshift Data API runs smoke SQL against loaded trend_features
     -> job compares Redshift values with curated/Athena
     -> writes validation-summary.json to S3
  -> PASS -> SmokeValidationPassed
  -> FAIL -> SNS alert -> PipelineFailed

CHECK MAPPING
1. Load completed successfully
   Step Functions Choice state.

2. Expected processing week exists
   Redshift COUNT(*) for processing_week_end must be > 0.

3. Row counts match curated/Athena
   Athena curated count compared with Redshift loaded count.

4. No unexpected duplicate rows
   Redshift groups by StockItemID + as_of_week_end_date and expects zero duplicate groups.

5. Required columns are populated
   Redshift checks critical columns for NULL and expects zero failing rows.

6. Key totals match curated data
   Athena and Redshift independently calculate units, sales, and profit totals.
   The Glue job compares them.

7. Table can be queried successfully
   Redshift Data API executes SELECT 1 FROM target_table LIMIT 1.

NOTE
The current AWS account is not opted in to Amazon Redshift, so the reference can be
inspected but cannot execute until a Redshift target is created/enabled later.
