# Terraform: opt-in adoption of recovered infrastructure

This directory **does not deploy by default**. Existing resources were created
manually and some have been intentionally deleted for cost control.

Read `../docs/DEPLOYMENT.md` and `../docs/ASSUMPTIONS.md` before modifying toggles.
The JSON in `recovered/` records actual AWS service metadata and IAM policy
snapshots. Do not edit these blindly; they are input to the opt-in IaC resources.

1. Install Terraform >= 1.6; use AWS account 672350744457.
2. `terraform init -backend=false` to validate WITHOUT adopting real state.
3. `terraform validate` and `terraform plan` with all flags false.
4. Only create/manage resources after preparing state backend, identifying
   existing cloud resources, and importing them with `terraform import`.
5. Never enable NAT, Redshift or MWAA without checking running costs.

The original `infra/` from the April demo is **not part of the current project**.
