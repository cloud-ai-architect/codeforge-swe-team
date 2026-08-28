# CodeForge

> Multi-agent software engineering team. Takes a GitHub issue, writes a fix, runs tests in a sandbox, opens a PR, and responds to review comments. Self-reflecting, with long-horizon planning.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Phase_1-yellow.svg)]()
[![Cloud](https://img.shields.io/badge/Cloud-AWS-orange.svg)]()
[![Region](https://img.shields.io/badge/Region-ap--south--1-yellow.svg)]()
[![Framework](https://img.shields.io/badge/Framework-Claude_Agent_SDK-FF6B6B.svg)]()
[![IaC](https://img.shields.io/badge/IaC-Terraform_≥1.9-7B42BC.svg)]()

---

## What this solves

AI coding assistants are great at single-file edits, but real engineering work requires:

- Reading an entire repo, understanding the build system, finding the right test to run
- Writing multi-file changes that preserve backwards compatibility
- Running tests in an isolated sandbox (so a bad code change can't crash the dev machine)
- Iterating on CI feedback
- Reviewing its own PR and fixing review comments
- Self-reflection after a task fails to learn what went wrong

CodeForge is a multi-agent SWE team that handles the full lifecycle of a code change, end-to-end.

```mermaid
graph LR
    A[GitHub Issue] --> B[Issue Triage Agent]
    B --> C[Planner Agent]
    C --> D[Code Writer Agent]
    D --> E[Sandbox Tester Agent]
    E -->|fails| D
    E -->|passes| F[Reviewer Agent]
    F -->|feedback| D
    F -->|approved| G[PR Creator Agent]
    G --> H[CI Watcher Agent]
    H -->|CI fails| D
    H -->|CI passes| I[Review Responder Agent]
    I --> D
    A -.merge.-> J[PR Merged]
```

## Key features

- **Multi-agent pipeline** — 8 specialized agents, each with a focused role
- **Sandboxed execution** — code runs in Fargate containers, no host access
- **Self-reflection** — agents review their own work and learn from failures
- **Long-horizon planning** — Planner Agent decomposes issues into subtasks
- **CI feedback loop** — automatically responds to test failures
- **GitHub-native** — uses GitHub API + webhooks for issue → PR → merge

## Architecture at a glance

```mermaid
graph TB
    subgraph Channels
        WH[GitHub Webhook]
    end
    subgraph Edge
        APIGW[API Gateway]
    end
    subgraph Compute
        SF[Step Function<br/>codeforge-pipeline]
        SA[Sandbox Fargate]
    end
    subgraph Storage
        S3S[Sandbox S3<br/>code clones]
        S3R[Results S3]
        DDB[Job State DDB]
    end
    WH --> SF
    APIGW --> SF
    SF --> SA
    SA --> S3S
    SA --> S3R
    SF --> DDB
```

Full architecture: [`docs/architecture/00-overview.md`](docs/architecture/00-overview.md).

## What you'll find here

| Area | Path |
|---|---|
| **ADRs** (decision log) | [`docs/adr/`](docs/adr/) |
| **Architecture** | [`docs/architecture/`](docs/architecture/) |
| **Runbooks** | [`docs/runbooks/`](docs/runbooks/) |

## Quick start

```bash
bash scripts/bootstrap.sh codeforge dev ap-south-1
cd infra/terraform
terraform init -backend-config="bucket=codeforge-tfstate-dev" \
                -backend-config="region=ap-south-1" \
                -backend-config="dynamodb_table=codeforge-tfstate-lock-dev"
terraform plan -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
```

## License

Apache 2.0 — see [`LICENSE`](LICENSE).
