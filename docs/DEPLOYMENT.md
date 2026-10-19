# Safe validation and deployment

**No deploy or terraform apply was performed during repository reconstruction.**

## 1. Create the dedicated GitHub repository

Create a PRIVATE empty repository `new-product-trend-data-platform` in your
GitHub account. This staging branch can then be copied to that repository,
without including the old demonstration files. Do not connect the existing
auto-deploying infrastructure pipeline to this repository until reviewed.

## 2. Static validation (no AWS access needed)
```sh
python -m compileall -q airflow reference tests
python scripts/validate_repository.py
python -m unittest discover -s tests -v
cd terraform
terraform fmt -recursive
terraform init -backend=false -input=false
terraform validate
```

## 3. Terraform state and imports

The current AWS account is 672350744457; the old April project's account ID
is **different**. NEVER copy the old backend or apply against the old state.

Review `terraform/backend.example.hcl`, copy it to `backend.hcl` only when
ready to adopt AWS resources, and run `terraform init
-backend-config=backend.hcl`. Remote state must be encrypted and locked.

All management flags default to false. State inventory / imports to prepare
before enabling each group include:
- Glue: 5 existing `reference-*` Glue job names
- S3: `novelty-margin-lakehouse-672350744457` bucket, versioning,
  encryption configuration and public access block
- IAM: 12 existing roles, 11 inline policies, attached managed-policy
  links, MWAA execution policy
- Glue catalog: `reference_new_product_trend` database, 5 catalog tables,
  structural Data Quality ruleset and Athena workgroups
- VPC `vpc-0d0dc20440ede602f`, subnets, IGW, route tables, SG and
  their associations/rules
- SNS: four pre-existing pipeline topics
- CI/CD: one existing CodePipeline and two existing CodeBuild projects
- Four pre-existing reference Step Functions workflows

For every resource: obtain the provider-specific import ID, import into
state, then `terraform plan` and reconcile drift before apply. Do not
bulk-enable all management flags, import the wrong account's state or
`terraform apply -auto-approve`.

**Important:** Terraform definitions recovered from the study environment
are a migration blueprint, not an automatically executable replacement for
every imported object. Reconcile names, tags, permissions and lifecycle
first. NAT resources cost money and should not be enabled without necessity.

## 4. Prepare source connectivity and scripts

- Create a least-privilege SQL Server read-only account; put its credentials
  in AWS Secrets Manager, not GitHub.
- Configure JDBC URL, private network route, DNS, outbound access, SG,
  Glue connection and SQL Server JDBC driver availability.
- Verify queries/columns in source_tables.json against actual SQL Server.
- Review the two newly authored jobs and test each independently with
  a controlled historical dataset.
- Stage pipeline files using manual CodeBuild. Deployment is denied by
  default unless ALLOW_PIPELINE_DEPLOY=true. No `terraform apply` runs in
  CodeBuild or GitHub CI.
- Update Glue/Athena catalog partition metadata and test all 23 SQL checks
  against the same processing window and raw source.
- Enable Redshift and MWAA only when ready; test least-privilege execution.

## 5. Bring up and validate

Progression: static tests -> Terraform provider plan -> source extraction
smoke -> raw validator -> transform -> staged DQ + reconciliation ->
promotion -> Redshift publish + smoke -> audit -> DAG full run.
Keep DAG paused until successful end-to-end validation.
