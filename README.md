# New Product Trend — Weekly AWS Data Platform

**Standalone rebuild candidate for a dedicated GitHub repository.** The old
April demonstration Terraform project is intentionally excluded.

This repository includes the latest 11-task MWAA DAG, seven Glue jobs (five
recovered unchanged from AWS, two newly authored), 23 recovered SQL checks,
data-quality rules, historical source contracts, reference Step Functions,
opt-in Terraform definitions, monitoring and gated CI/CD.

**Operational status: CODE / STUDY IMPLEMENTATION, NOT LIVE DEPLOYED.**
No SQL Server Glue connection exists in the target AWS account. The MWAA
environment was deliberately deleted for cost reasons and Redshift was never
deployed. Five reference jobs have no recorded runs. Do not call this
production-tested or deploy all Terraform resources without importing the
existing resources and reviewing cost/security.

## Architecture

```text
SQL Server (read-only JDBC, Secrets Manager)
 -> extract_source_to_raw_s3             (NEW reference-raw-ingest)
 -> validate_raw_data                    (recovered)
 -> transform_to_staging                 (NEW PySpark history / cohort mart)
 -> validate_staged_data                 (recovered Glue DQ + Athena SQL)
 -> promote_validated_to_curated         (recovered)
 -> publish_curated_to_redshift          (recovered, optional Redshift)
 -> post_load_smoke_validation           (recovered)
 -> record_pipeline_audit                (DAG/S3)
```

The DAG also includes start, processing-window, and end tasks, for 11 tasks.
Its timezone is America/New_York, Sundays at 02:00, catchup disabled and paused
when first installed.

## Start here

- [Architecture and pipeline contracts](docs/ARCHITECTURE.md)
- [Recovery status, source assumptions and limitations](docs/ASSUMPTIONS.md)
- [Safe validation, state import and deployment](docs/DEPLOYMENT.md)
- [Terraform readme](terraform/README.md)

```sh
python -m compileall -q airflow reference tests
python scripts/validate_repository.py
python -m unittest discover -s tests -v
cd terraform
terraform init -backend=false
terraform validate
```

All optional Terraform management toggles default to **false** to protect
pre-existing AWS resources and avoid restoring expensive services accidentally.
Never commit state files, credentials, or real source extracts.
