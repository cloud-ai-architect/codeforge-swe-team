# Security Policy

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a vulnerability

**Please do NOT file a public GitHub issue for security vulnerabilities.**

Report via GitHub Security Advisories: https://github.com/cloud-ai-architect/codeforge-swe-team/security/advisories/new

Include description, impact, repro, affected versions.

## Response timeline

48h ack, 7d triage, 14d patch for High/Critical.

## Security model

- GitHub OIDC for AWS (no long-lived credentials)
- Sandbox code runs in isolated Fargate containers (network-restricted)
- Gitleaks pre-commit + CI
- IAM scoped to `Project=codeforge` tag
- All buckets encrypted at rest
- TLS 1.2+ in transit
