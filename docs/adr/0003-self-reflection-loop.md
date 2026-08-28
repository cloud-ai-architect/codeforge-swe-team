# ADR-0003: Implement explicit self-reflection loop in agents

- **Status**: Accepted
- **Date**: 2026-08-28
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: agents, architecture, quality

## Context and problem statement

A Code Agent that just tries once will fail on most real-world tasks. The literature on SWE-bench and similar benchmarks shows that **iterative self-correction** is the single biggest performance multiplier.

CodeForge agents need to:
- After a failed test, analyze *why* it failed
- After a bad code review, understand *what* the reviewer is concerned about
- After CI failure, distinguish between test bug and code bug
- After task timeout, prioritize what to attempt next

## Decision drivers

- Higher pass rate on real tasks
- Better resilience to partial failures
- Learning from mistakes over time
- Predictable behavior (no infinite loops)

## Considered options

### Option 1: Explicit self-reflection loop (chosen)

- ✅ Deterministic, observable
- ✅ Budget-bounded (max N retries)
- ✅ Traces stored for analysis
- ✅ Improves over time with prompt tuning

### Option 2: Implicit reflection (single attempt)

- ✅ Simpler
- ❌ Lower pass rate

### Option 3: External critic agent

- ✅ More sophisticated
- ❌ More complex, more cost

## Decision outcome

**Chosen option 1: Explicit self-reflection loop** with bounded retries.

Pattern:
```
1. Attempt action
2. Observe result (test output, review comment, CI log)
3. Reflect: "Why did this fail? What would I do differently?"
4. Adjust plan
5. Retry (up to MAX_RETRIES)
6. If still fails: escalate to human
```

### Consequences

**Positive**

- 2-3× higher pass rate vs single attempt
- Each failure leaves a trace for analysis
- Bounded cost (max retries = max cost)

**Negative**

- More tokens used (more cost)
- Slower on hard tasks

### Confirmation

- 80%+ pass rate on held-out test set
- p95 retries to success: 2
- Cost overhead from retries: < 30%

## Pros and cons of the options

| Option | Pass rate | Cost | Complexity | Traceability |
|---|---|---|---|---|
| **Self-reflection** | ✅ 80%+ | ⚠️ 1.3× | Medium | ✅ Full trace |
| Single attempt | ⚠️ 50% | ✅ 1.0× | Low | ✅ Minimal |
| External critic | ✅ 85%+ | ❌ 2× | High | ✅ Full trace |

## References

- [Reflexion (Shinn et al., 2023)](https://arxiv.org/abs/2303.11381)
- [SWE-bench Verified leaderboard](https://www.swebench.com/)
- [Anthropic Building Effective Agents](https://docs.claude.com/en/docs/build-with-claude/build-effective-agents)
