locals {
  recovered_roles     = jsondecode(file(format("%s/recovered/iam_roles.json", path.module)))
  recovered_jobs      = { for j in jsondecode(file(format("%s/recovered/glue_jobs.json", path.module))).jobs : j.Name => j }
  recovered_catalog   = jsondecode(file(format("%s/recovered/catalog.json", path.module)))
  recovered_network   = jsondecode(file(format("%s/recovered/network.json", path.module)))
  recovered_workflows = jsondecode(file(format("%s/recovered/stepfunctions_roles.json", path.module)))
  role_inline = {
    for p in flatten([
      for name, config in local.recovered_roles : [
        for inline in config.inline : {
          key    = format("%s--%s", name, inline.name)
          role   = name
          name   = inline.name
          policy = inline.policy
        }
      ]
    ]) : p.key => p
  }
  role_attachments = {
    for p in flatten([
      for name, config in local.recovered_roles : [
        for arn in config.attached : {
          key  = format("%s--%s", name, replace(arn, ":", "-"))
          role = name
          arn  = arn
        }
      ]
    ]) : p.key => p
  }
}
