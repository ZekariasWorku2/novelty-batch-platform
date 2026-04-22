locals {
  name_prefix = "${var.project}-${var.environment}"

  cidr_block = "10.40.0.0/16"

  azs = slice(data.aws_availability_zones.available.names, 0, 2)

  public_subnets  = ["10.40.0.0/24", "10.40.1.0/24"]
  private_subnets = ["10.40.10.0/24", "10.40.11.0/24"]
}