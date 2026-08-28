# CodeForge Deploy Runbook

## Deploy to a new AWS account

```bash
# 1. Clone
git clone https://github.com/cloud-ai-architect/codeforge-swe-team.git
cd codeforge-swe-team

# 2. Bootstrap
bash scripts/bootstrap.sh codeforge dev ap-south-1

# 3. Init + apply
cd infra/terraform
terraform init -backend-config="bucket=codeforge-tfstate-dev" \
                -backend-config="region=ap-south-1" \
                -backend-config="dynamodb_table=codeforge-tfstate-lock-dev"
terraform plan -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
```

## Required GitHub App setup

1. Create a GitHub App at https://github.com/settings/apps/new
2. Permissions: `Read & Write` on Issues, Pull Requests, Contents
3. Subscribe to events: `Issues`, `Issue comments`, `Pull request reviews`, `Pull request review comments`
4. Install the App on your target repositories
5. Save the App ID and private key

## Required GitHub secrets

- `GITHUB_APP_ID`
- `GITHUB_APP_PRIVATE_KEY`
- `GITHUB_WEBHOOK_SECRET`
- `AWS_DEPLOY_ROLE_ARN`
- `AWS_REGION`
