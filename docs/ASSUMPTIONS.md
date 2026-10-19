# Recovery, assumptions, operational gaps

## Verified AWS recovery
- DAG: exact S3 bytes recovered and previously verified against existing
  `mwaa-production-study` GitHub branch.
- Five Glue jobs: scripts and live `GetJob` configurations are recovered.
- Twenty-three SQL scripts, Glue Data Quality DQDL, JSON config, reference
  threshold CSV and four Step Functions state machine definitions recovered.
- IAM role and policy snapshots, codepipeline/build configs, Glue catalog,
  network and Athena metadata recovered under `terraform/recovered/`.

## Newly authored, not recovered
- `reference/raw-ingest/scripts/raw_ingest.py` (SQL Server JDBC extraction).
- `reference/raw-ingest/config/source_tables.json` (assumed WWI SQL aliases).
- `reference/transform/scripts/transform_to_staging.py` (PySpark cohort mart).
- Optional Terraform / CI/CD wrappers reconstructed from AWS configuration.

## Important blockers to live execution
1. AWS has **no SQL Server Glue connection or credential secret**.
   Supply networking, Secrets Manager ARN, SQL Server endpoint/database and
   validate the assumed queries against the real source schema.
2. No MWAA environment or Redshift cluster/workgroup exists. These were
   deliberately absent/deleted and remain opt-in because of costs.
3. Five recovered reference Glue jobs have **no recorded runs**. New jobs
   have never executed against the source either.
4. Athena catalog tables and stored SQL refer to an earlier landing dataset;
   reconcile raw/staged catalog registration and feature logic before using
   them as the acceptance gate.
5. Source snapshots are re-read each time. Scale/CDC/backfills/historical
   revisions require explicit design. The new transform assumes sales source
   history is complete, product launch = first observed sale, and the full
   eight-week cohort is populated only when complete.
6. Source master-data snapshots are overwritten weekly as separate S3
   versions and de-duplicated by product ID without true point-in-time joins.
   Production ML feature correctness requires as-of joins to historical
   product attributes. Historical validation SQL may need adjustment.
7. Existing route table has a blackhole route to a deleted NAT. The
   configuration does not restore NAT or MWAA automatically.
8. Terraform reference config contains existing resources **not imported
   to state**. Enabling a management flag before importing can cause
   CreateAlreadyExists or replacement errors. Review plan in each stage.
9. AWS CodeConnection availability is not proof of new-repository
   authorization. Re-authorize GitHub access as needed.
10. Some provider settings (MWAA Airflow version, Redshift minimum
    capacity and private networking) require account/region validation
    before resource creation.

## Security and privacy

No database passwords, access keys or extracted business rows belong in Git.
Recovered IAM and network snapshots are sensitive operational metadata.
**Publish the dedicated repository as PRIVATE**.
