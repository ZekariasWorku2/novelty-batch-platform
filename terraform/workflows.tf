# Auxiliary reference Step Functions are recovered as exact ASL JSON.
# No automatic triggers or schedules; MWAA is the primary pipeline orchestrator.
locals {
  reference_state_machines = toset([
    "reference-raw-data-validation-gate",
    "reference-staged-data-validation-gate",
    "reference-curated-to-redshift-publish",
    "reference-redshift-postload-smoke-validation-gate"
  ])
}
resource "aws_sfn_state_machine" "reference" {
  for_each  = var.manage_workflows ? local.reference_state_machines : toset([])
  name      = each.key
  role_arn  = local.recovered_workflows[each.key]
  definition = file(format("%s/../stepfunctions/%s.asl.json", path.module, each.key))
  type      = "STANDARD"
  lifecycle {
    prevent_destroy = true
  }
}
