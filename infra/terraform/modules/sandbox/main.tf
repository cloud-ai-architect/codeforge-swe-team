###############################################################################
# Fargate sandbox for executing model-authored code.
#
# This is the one component that cannot be a Lambda. Running code a model
# just wrote needs a boundary Lambda does not provide: Lambda has outbound
# internet by default, a writable filesystem, and an execution role that the
# generated code inherits.
#
# The isolation here is structural rather than advisory:
#
#   - The subnet is private with no NAT gateway and no internet gateway
#     route, so there is no path off the VPC even if egress were allowed.
#   - The security group allows no egress at all.
#   - The root filesystem is read-only; scratch space is a small tmpfs that
#     does not survive the task.
#   - The container runs as a non-root user.
#   - The task role grants nothing. Code that escapes the interpreter still
#     holds no AWS permissions. Only the *execution* role can pull the image
#     and write logs, and that role is not exposed to the running code.
###############################################################################

terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

variable "name_prefix" { type = string }

# The sandbox is the most expensive component in this portfolio: three
# interface VPC endpoints at roughly $7/month each, which is what buys the
# task genuine network isolation. It is therefore opt-in. Everything else in
# the project costs nothing when idle.
variable "enabled" {
  type    = bool
  default = false
}
variable "cpu" {
  type    = string
  default = "512"
}
variable "memory" {
  type    = string
  default = "1024"
}
# Pulled through the private registry below rather than direct from public
# ECR: the sandbox subnet has no internet route, so a public image reference
# can never be resolved from inside it.
variable "runner_image_upstream" {
  type    = string
  default = "docker/library/python:3.12-slim"
}
variable "log_retention_days" {
  type    = number
  default = 14
}
variable "common_tags" {
  type    = map(string)
  default = {}
}

# --- Network: private, with no route to the internet ---

resource "aws_vpc" "this" {
  count = var.enabled ? 1 : 0

  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(var.common_tags, { Name = "${var.name_prefix}-sandbox-vpc" })
}

# Deliberately no aws_internet_gateway and no aws_nat_gateway. The default
# route table has only the local VPC route, so tasks have nowhere to go.
resource "aws_subnet" "sandbox" {
  count = var.enabled ? 1 : 0

  vpc_id            = aws_vpc.this[0].id
  cidr_block        = "10.42.1.0/24"
  availability_zone = "${data.aws_region.current.name}a"

  tags = merge(var.common_tags, { Name = "${var.name_prefix}-sandbox-subnet" })
}

data "aws_region" "current" {}

data "aws_prefix_list" "s3" {
  name = "com.amazonaws.${data.aws_region.current.name}.s3"
}

resource "aws_security_group" "sandbox" {
  count = var.enabled ? 1 : 0

  name        = "${var.name_prefix}-sandbox"
  description = "No ingress, no egress. Sandboxed code has no network access."
  vpc_id      = aws_vpc.this[0].id

  # No ingress.
  #
  # Egress is limited to HTTPS to the VPC endpoint security group and nothing
  # else. This is not a loophole: the ECS agent shares the task ENI, so with
  # zero egress it cannot pull the image either -- the task sits in
  # PROVISIONING until the caller times out, which is what happened here.
  #
  # The endpoints reach only ECR and CloudWatch Logs, and the subnet has no
  # internet gateway or NAT, so the task still has no route to the internet.
  egress {
    description     = "HTTPS to interface endpoints (ECR API, ECR DKR, Logs)"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.endpoints[0].id]
  }

  # ECR stores image layers in S3 and redirects the pull there. That traffic
  # goes through the S3 *gateway* endpoint, which is reached by route-table
  # prefix list rather than by an ENI -- so the security_groups rule above
  # does not cover it. Without this the pull fails partway through with
  # "dial tcp 52.219.x.x:443: i/o timeout", having already talked to ECR.
  #
  # A prefix list keeps this scoped to S3 in this region; it is not egress to
  # the internet.
  egress {
    description     = "HTTPS to S3 gateway endpoint (ECR image layers)"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    prefix_list_ids = [data.aws_prefix_list.s3.id]
  }

  tags = merge(var.common_tags, { Name = "${var.name_prefix}-sandbox-sg" })
}

# --- VPC endpoints ---
#
# The subnet has no internet route, which is the point -- but the ECS agent
# still has to pull the image and ship logs. Without these the task never
# leaves PROVISIONING and eventually times out, which is exactly what
# happened on the first deploy.
#
# Interface endpoints reach ECR and CloudWatch Logs over PrivateLink, and the
# S3 gateway endpoint carries the image layers. The result is that the ECS
# agent can do its job while the *task* still has no route to the internet:
# the security group below permits only HTTPS to the endpoints, and the
# sandbox security group permits nothing at all.
#
# These are the most expensive part of this project (~$7/month per interface
# endpoint), which is why the whole module is opt-in. See var.enabled.

resource "aws_security_group" "endpoints" {
  count = var.enabled ? 1 : 0

  name        = "${var.name_prefix}-sandbox-endpoints"
  description = "HTTPS from the sandbox subnet to VPC endpoints"
  vpc_id      = aws_vpc.this[0].id

  ingress {
    description = "HTTPS from sandbox tasks"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_subnet.sandbox[0].cidr_block]
  }

  tags = merge(var.common_tags, { Name = "${var.name_prefix}-sandbox-endpoints" })
}

resource "aws_vpc_endpoint" "interface" {
  for_each = var.enabled ? toset(["ecr.api", "ecr.dkr", "logs"]) : toset([])

  vpc_id              = aws_vpc.this[0].id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.${each.value}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.sandbox[0].id]
  security_group_ids  = [aws_security_group.endpoints[0].id]
  private_dns_enabled = true

  tags = merge(var.common_tags, { Name = "${var.name_prefix}-${each.value}" })
}

# Gateway endpoint: no hourly charge, and ECR image layers come from S3.
resource "aws_vpc_endpoint" "s3" {
  count = var.enabled ? 1 : 0

  vpc_id            = aws_vpc.this[0].id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_vpc.this[0].default_route_table_id]

  tags = merge(var.common_tags, { Name = "${var.name_prefix}-s3" })
}

# ECR pull-through cache.
#
# The task has no route to public ECR, so the image reference has to resolve
# inside the VPC. A pull-through cache makes ECR fetch the upstream image on
# our behalf and serve it from the private registry, which the ECR endpoints
# above can reach. The task still has no internet access; ECR does the
# fetching, not the task.
resource "aws_ecr_pull_through_cache_rule" "public" {
  count = var.enabled ? 1 : 0

  # ECR caps this at 30 characters, which "${var.name_prefix}-upstream"
  # overflows for longer project names.
  ecr_repository_prefix = substr("${var.name_prefix}-up", 0, 30)
  upstream_registry_url = "public.ecr.aws"
}

locals {
  runner_image = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${data.aws_region.current.name}.amazonaws.com/${substr("${var.name_prefix}-up", 0, 30)}/${var.runner_image_upstream}"
}

data "aws_caller_identity" "current" {}

# --- Cluster and task ---

resource "aws_ecs_cluster" "this" {
  count = var.enabled ? 1 : 0

  name = "${var.name_prefix}-sandbox"
  tags = var.common_tags
}

resource "aws_cloudwatch_log_group" "sandbox" {
  count = var.enabled ? 1 : 0

  name              = "/ecs/${var.name_prefix}-sandbox"
  retention_in_days = var.log_retention_days
  tags              = var.common_tags
}

# Execution role: pulls the image and writes logs. This belongs to the ECS
# agent, not to the running code.
data "aws_iam_policy_document" "execution_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  count = var.enabled ? 1 : 0

  name               = "${var.name_prefix}-sandbox-execution"
  assume_role_policy = data.aws_iam_policy_document.execution_assume.json
  tags               = var.common_tags
}

resource "aws_iam_role_policy_attachment" "execution" {
  count = var.enabled ? 1 : 0

  role       = aws_iam_role.execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Pull-through cache creates the mirrored repository on first pull, and
# AmazonECSTaskExecutionRolePolicy does not grant that. Without these the
# task sits in PROVISIONING until the caller times out, with no container
# reason to explain why.
data "aws_iam_policy_document" "execution_pullthrough" {
  statement {
    sid    = "PullThroughCache"
    effect = "Allow"

    actions = [
      "ecr:CreateRepository",
      "ecr:BatchImportUpstreamImage",
      "ecr:GetAuthorizationToken",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:TagResource",
    ]

    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "execution_pullthrough" {
  count = var.enabled ? 1 : 0

  name   = "pull-through-cache"
  role   = aws_iam_role.execution[0].id
  policy = data.aws_iam_policy_document.execution_pullthrough.json
}

# Task role: intentionally empty. The sandboxed process assumes this role,
# and it can do nothing.
resource "aws_iam_role" "task" {
  count = var.enabled ? 1 : 0

  name               = "${var.name_prefix}-sandbox-task"
  assume_role_policy = data.aws_iam_policy_document.execution_assume.json
  tags               = var.common_tags
}

resource "aws_ecs_task_definition" "runner" {
  count = var.enabled ? 1 : 0

  family                   = "${var.name_prefix}-sandbox"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.execution[0].arn
  task_role_arn            = aws_iam_role.task[0].arn

  container_definitions = jsonencode([
    {
      name      = "runner"
      image     = local.runner_image
      essential = true

      readonlyRootFilesystem = true
      user                   = "65534:65534" # nobody

      linuxParameters = {
        initProcessEnabled = true
      }

      # Scratch space that does not outlive the task.
      mountPoints = [{
        sourceVolume  = "scratch"
        containerPath = "/tmp"
        readOnly      = false
      }]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.sandbox[0].name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "sandbox"
        }
      }
    }
  ])

  volume {
    name = "scratch"
  }

  tags = var.common_tags
}

output "enabled" { value = var.enabled }

output "cluster_name" {
  value = var.enabled ? aws_ecs_cluster.this[0].name : ""
}

output "task_definition" {
  value = var.enabled ? aws_ecs_task_definition.runner[0].arn : ""
}

output "subnet_ids" {
  value = var.enabled ? [aws_subnet.sandbox[0].id] : []
}

output "security_group_id" {
  value = var.enabled ? aws_security_group.sandbox[0].id : ""
}

output "log_group" {
  value = var.enabled ? aws_cloudwatch_log_group.sandbox[0].name : ""
}
