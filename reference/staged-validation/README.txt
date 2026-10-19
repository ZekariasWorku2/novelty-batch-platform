STAGED DATA COMPREHENSIVE VALIDATION - REFERENCE ARCHITECTURE

This is an idle reference setup. Nothing is scheduled and nothing has been executed.

FLOW
Transformation -> staged Parquet -> Step Functions
  -> Glue validation job
     -> Spark readability/schema/row-count checks
     -> Glue Data Quality structural/null/range rules
     -> Athena SQL calculation/reconciliation/business-rule checks
  -> PASS -> promotion Glue job -> trusted curated S3
  -> FAIL -> SNS alert -> pipeline fails; staged data remains for investigation

SERVICES
S3: scripts, configs, SQL, audit/results
Glue Data Catalog: reference staged table
Glue Data Quality: structural/range ruleset
Athena: validation workgroup and saved queries
Glue ETL: validation and promotion job definitions
Step Functions: PASS/FAIL orchestration
SNS: failure topic
IAM: service roles

EXPECTED ATHENA BEHAVIOR
Every saved validation query returns one column named failure_count.
0 = PASS. Any non-zero value = FAIL.
