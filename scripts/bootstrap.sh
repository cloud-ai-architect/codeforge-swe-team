#!/usr/bin/env bash
# CodeForge bootstrap — same pattern as other projects.
set -euo pipefail

PROJECT="${1:-codeforge}"
ENV="${2:-dev}"
REGION="${3:-ap-south-1}"
GITHUB_ORG="${4:-cloud-ai-architect}"
GITHUB_REPO="${5:-codeforge-swe-team}"

STATE_BUCKET="${PROJECT}-tfstate-${ENV}"
LOCK_TABLE="${PROJECT}-tfstate-lock-${ENV}"
ROLE_NAME="${PROJECT}-github-deploy-role-${ENV}"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
OIDC_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"

# 1. State bucket
if ! aws s3api head-bucket --bucket "$STATE_BUCKET" --region "$REGION" 2>/dev/null; then
  [ "$REGION" = "us-east-1" ] && aws s3api create-bucket --bucket "$STATE_BUCKET" || \
    aws s3api create-bucket --bucket "$STATE_BUCKET" --region "$REGION" --create-bucket-configuration LocationConstraint="$REGION"
fi
aws s3api put-bucket-versioning --bucket "$STATE_BUCKET" --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "$STATE_BUCKET" --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-public-access-block --bucket "$STATE_BUCKET" --public-access-block-configuration '{"BlockPublicAcls":true,"IgnorePublicAcls":true,"BlockPublicPolicy":true,"RestrictPublicBuckets":true}'

# 2. Lock table
if ! aws dynamodb describe-table --table-name "$LOCK_TABLE" --region "$REGION" >/dev/null 2>&1; then
  aws dynamodb create-table --table-name "$LOCK_TABLE" --attribute-definitions AttributeName=LockID,AttributeType=S --key-schema AttributeName=LockID,KeyType=HASH --billing-mode PAY_PER_REQUEST --region "$REGION"
fi

# 3. OIDC
if ! aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_ARN" >/dev/null 2>&1; then
  aws iam create-open-id-connect-provider --url https://token.actions.githubusercontent.com --client-id-list sts.amazonaws.com --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
fi

# 4. IAM role
cat > /tmp/trust.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "$OIDC_ARN" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": [
          "repo:${GITHUB_ORG}/${GITHUB_REPO}:ref:refs/heads/main",
          "repo:${GITHUB_ORG}/${GITHUB_REPO}:pull_request"
        ]
      }
    }
  }]
}
EOF

if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document file:///tmp/trust.json
  cat > /tmp/perm.json <<EOF
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"*","Resource":"*","Condition":{"StringEquals":{"aws:ResourceTag/Project":"$PROJECT"}}}]}
EOF
  aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name "${PROJECT}-deploy" --policy-document file:///tmp/perm.json
fi

echo "==> Bootstrap complete"
echo "  State bucket:  s3://$STATE_BUCKET"
echo "  Lock table:    $LOCK_TABLE"
echo "  Deploy role:   $ROLE_NAME"
echo
echo "Next: add AWS_DEPLOY_ROLE_ARN and AWS_REGION secrets to GitHub."
echo "Then: cd infra/terraform && terraform init && terraform apply"
