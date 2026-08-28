# ADR-0002: Run code execution sandbox in Fargate Spot

- **Status**: Accepted
- **Date**: 2026-08-28
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: compute, security, sandbox

## Context and problem statement

The Code Writer and Test Runner agents need to execute code. This includes:

- Cloning the repository
- Installing dependencies
- Running tests
- Building artifacts

The execution must be **isolated** (can't affect the host or other tasks) and **safe** (can't reach the public internet except for known package registries).

## Decision drivers

- Strong isolation (can't affect other tasks)
- Cheap (most runs are < 5 min)
- Reproducible (same env every time)
- Network-restricted (only allowed package registries)
- AWS-native

## Considered options

### Option 1: Fargate Spot (chosen)

- ✅ AWS-native, isolated
- ✅ Spot pricing ~70% cheaper
- ✅ Network ACLs for egress filtering
- ✅ Custom container image
- ⚠️ Cold start ~30s
- ⚠️ Can be interrupted (Spot)

### Option 2: Lambda

- ✅ Fast cold start
- ❌ 15-min timeout (too short for complex test suites)
- ❌ Limited /tmp (512 MB) — npm install often fails
- ❌ No Docker image (deployment package only)

### Option 3: EC2 Spot

- ✅ Persistent (no cold start)
- ❌ Manual lifecycle management
- ❌ Harder to enforce network policies

### Option 4: LocalStack / Mock

- ✅ Free
- ❌ Doesn't test the real build
- ❌ Misses integration bugs

## Decision outcome

**Chosen option 1: Fargate Spot** with a custom container image.

Container image:
- Base: `python:3.12-slim` (for Python) OR `node:20-slim` (for JS) — task picks based on repo
- Pre-installed: `git`, `curl`, `aws-cli`, common build tools
- Network: only egress to `pypi.org`, `npmjs.com`, `github.com` via VPC endpoint or NACL
- Working directory: mounted from S3
- Resource limits: 2 vCPU, 4 GB RAM (Spot interruptable)

### Consequences

**Positive**

- Strong isolation (ECS task per execution)
- Cheap (~$0.005 per task at 5 min)
- Reproducible (custom container)
- AWS-native

**Negative**

- ~30s cold start per task
- Spot can be interrupted (handle with retry)
- Custom image maintenance

### Confirmation

- p95 sandbox startup < 35s
- Cost < $0.01 per task
- 0% malicious code escapes (tested with deliberate malicious inputs)

## Pros and cons of the options

| Option | Isolation | Cold start | Cost | Max runtime |
|---|---|---|---|---|
| **Fargate Spot** | ✅ Strong | 30s | ✅ $0.005/task | ✅ Unlimited |
| Lambda | ✅ Strong | <1s | ✅ Cheap | ❌ 15 min |
| EC2 Spot | ✅ Strong | 60s | ⚠️ $0.01/hr min | ✅ Unlimited |
| LocalStack | ❌ None | <1s | ✅ Free | ✅ Unlimited |

## References

- [AWS Fargate Spot](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-spot.html)
- [ECS task networking](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-networking.html)
- [SWE-bench sandboxed execution](https://www.swebench.com/)
