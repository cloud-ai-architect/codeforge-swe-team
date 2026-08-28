# Architecture Overview

CodeForge is a multi-agent SWE team that takes a GitHub issue and produces a merged PR. The system uses a Step Function to coordinate 8 specialized agents, with Fargate Sandboxes for safe code execution.

## System context

```mermaid
graph TB
    subgraph External
        GH[GitHub]
        Dev[Developer]
    end

    subgraph CF[CodeForge]
        Webhook[GitHub Webhook]
        SF[Step Function]
        Sandbox[Fargate Sandbox]
        Storage[Storage Layer]
    end

    GH -->|issue opened| Webhook
    Webhook --> SF
    SF --> Sandbox
    Sandbox -->|test results| SF
    SF -->|PR created| GH
    Dev -->|review comments| GH
    GH -->|PR comments| Webhook
    SF --> Storage
```

## High-level architecture

```mermaid
graph LR
    subgraph Compute
        SF[Step Function<br/>codeforge-pipeline]
        Sandbox[Fargate Sandbox<br/>2 vCPU / 4GB]
    end
    subgraph Agents[Agents]
        IT[Issue Triage]
        PL[Planner]
        CW[Code Writer]
        ST[Sandbox Tester]
        RV[Reviewer]
        PR[PR Creator]
        CW2[CI Watcher]
        RR[Review Responder]
    end
    subgraph Storage
        S3S[Sandbox S3]
        DDB[Job State DDB]
    end

    IT --> PL --> CW --> ST
    ST -->|fail| CW
    ST -->|pass| RV
    RV -->|feedback| CW
    RV -->|approved| PR
    PR --> CW2
    CW2 -->|fail| CW
    CW2 -->|pass| RR
    RR --> CW
```

## Pipeline stages

1. **Issue Triage** — fetch the issue, understand it
2. **Planner** — decompose into 3-7 subtasks
3. **Code Writer** (loop) — write code, get review feedback
4. **Sandbox Tester** — run tests in isolated env
5. **Reviewer** — self-review; if approved → PR Creator, else → Code Writer
6. **PR Creator** — open the PR
7. **CI Watcher** — wait for CI; if fail → Code Writer
8. **Review Responder** — address review comments

## Why this design

| Concern | Decision | Why |
|---|---|---|
| Long-horizon | Claude Agent SDK | Best for SWE-bench-style |
| Self-reflection | Explicit retry loop | 2-3× better pass rate |
| Isolation | Fargate Spot | Strong isolation, cheap |
| State | DynamoDB | Cheap, queryable |
| Code | S3 + Git | Native GitHub integration |

## Where to read next

- [HLD](01-hld.md) — Service boundaries
- [LLD](02-lld.md) — Data shapes
- [Security model](06-security-model.md) — Trust boundaries
