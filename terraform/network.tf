# Inventory: existing VPC 10.20.0.0/16, two public and two private subnets.
# No NAT gateway remains; the old private route currently points to a deleted NAT.
# All pre-existing objects MUST be imported into state before manage_existing_network=true.
resource "aws_vpc" "study" {
  count                = var.manage_existing_network ? 1 : 0
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "new-product-trend-vpc" }
  lifecycle {
    prevent_destroy = true
  }
}
locals {
  network_subnets = {
    public_a  = { cidr = "10.20.0.0/24", az = "us-east-1a", public = true }
    public_b  = { cidr = "10.20.1.0/24", az = "us-east-1b", public = true }
    private_a = { cidr = "10.20.10.0/24", az = "us-east-1a", public = false }
    private_b = { cidr = "10.20.11.0/24", az = "us-east-1b", public = false }
  }
}
resource "aws_subnet" "study" {
  for_each                = { for k, v in local.network_subnets : k => v if var.manage_existing_network }
  vpc_id                  = aws_vpc.study[0].id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = each.value.public
  tags                    = { Name = "new-product-trend-${each.key}" }
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_internet_gateway" "study" {
  count  = var.manage_existing_network ? 1 : 0
  vpc_id = aws_vpc.study[0].id
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_route_table" "public" {
  count  = var.manage_existing_network ? 1 : 0
  vpc_id = aws_vpc.study[0].id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.study[0].id
  }
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_route_table" "private" {
  count  = var.manage_existing_network ? 1 : 0
  vpc_id = aws_vpc.study[0].id
  # Do NOT reintroduce the blackholed NAT route automatically.
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_route_table_association" "public" {
  for_each       = { for k,v in local.network_subnets : k => v if var.manage_existing_network && v.public }
  subnet_id      = aws_subnet.study[each.key].id
  route_table_id = aws_route_table.public[0].id
}
resource "aws_route_table_association" "private" {
  for_each       = { for k,v in local.network_subnets : k => v if var.manage_existing_network && !v.public }
  subnet_id      = aws_subnet.study[each.key].id
  route_table_id = aws_route_table.private[0].id
}
resource "aws_security_group" "mwaa" {
  count       = var.manage_existing_network ? 1 : 0
  name        = "new-product-trend-mwaa-sg"
  description = "MWAA workers and scheduler security group"
  vpc_id      = aws_vpc.study[0].id
  tags        = { Name = "new-product-trend-mwaa-sg" }
  lifecycle {
    prevent_destroy = true
  }
}
resource "aws_vpc_security_group_ingress_rule" "mwaa_self" {
  count                        = var.manage_existing_network ? 1 : 0
  security_group_id            = aws_security_group.mwaa[0].id
  referenced_security_group_id = aws_security_group.mwaa[0].id
  ip_protocol                  = "-1"
}
resource "aws_vpc_security_group_egress_rule" "mwaa_out" {
  count             = var.manage_existing_network ? 1 : 0
  security_group_id = aws_security_group.mwaa[0].id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
# New NAT is opt-in and billable. Use existing public subnet; route requires
# separate explicitly managed aws_route association review, not auto-changed.
resource "aws_eip" "nat" {
  count  = var.enable_nat ? 1 : 0
  domain = "vpc"
}
resource "aws_nat_gateway" "new" {
  count         = var.enable_nat ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = var.public_subnet_id
  depends_on    = [aws_internet_gateway.study]
}
