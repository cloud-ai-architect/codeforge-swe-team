aws_region             = "ap-south-1"
environment            = "dev"
project_name           = "codeforge-swe-team"
owner                  = "vijay"
cost_center            = "portfolio"
github_org             = "cloud-ai-architect"
github_repo            = "codeforge-swe-team"
bedrock_model_id       = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
bedrock_haiku_model_id = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
embedding_dimensions   = 1024
lambda_runtime         = "python3.12"
lambda_memory_mb       = 512
lambda_timeout_seconds = 300
enable_cloudfront      = true
log_retention_days     = 30
monthly_budget_usd     = 50

# The Fargate execution sandbox. Costs roughly $21/month for the three
# interface VPC endpoints it needs to pull an image without a NAT gateway.
# Everything else in this stack is idle-free.
sandbox_enabled = true
