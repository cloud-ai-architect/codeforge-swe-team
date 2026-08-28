# ADR-0001: Use Claude Agent SDK as the primary framework

- **Status**: Accepted
- **Date**: 2026-08-28
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: agents, framework

## Context and problem statement

CodeForge is a multi-agent system that takes a GitHub issue, writes a fix, runs tests, opens a PR, and responds to reviews. The agents need:

- Long-horizon planning (decompose a feature into 5-10 subtasks)
- Self-reflection (after failure, analyze why and adjust)
- Tool use (read/write files, run shell, call GitHub API)
- Computer use (browser-based, for docs/sites)
- Sub-agent isolation (each agent has its own context)

## Decision drivers

- Long-horizon planning is the core requirement (SWE-bench-style tasks)
- Self-reflection for iterative improvement
- Native Claude Sonnet 4.5 / Opus 4 support
- Computer use for documentation lookups
- Sub-agent isolation for parallel work

## Considered options

### Option 1: Claude Agent SDK (chosen)

- ✅ **Built for SWE-bench-style tasks** — long horizon, self-reflection
- ✅ Native computer use
- ✅ Sub-agent isolation
- ✅ First-class Claude support
- ✅ Maintained by Anthropic
- ⚠️ Anthropic-specific (less portable)

### Option 2: LangGraph

- ✅ Mature, flexible
- ✅ Sub-agent patterns
- ⚠️ More boilerplate for long-horizon patterns
- ⚠️ No native computer use

### Option 3: CrewAI

- ✅ Easy multi-agent
- ⚠️ Not designed for SWE-style long-horizon
- ⚠️ No native computer use

### Option 4: OpenAI Agents SDK

- ✅ Official OpenAI
- ❌ OpenAI-only at model layer

## Decision outcome

**Chosen option 1: Claude Agent SDK** for primary orchestration. Use Bedrock as the model provider (Claude Sonnet 4.5 + Claude Opus 4 for hard tasks).

### Consequences

**Positive**

- Best-in-class for SWE-bench-style tasks
- Self-reflection built in
- Computer use for docs
- Sub-agent isolation

**Negative**

- Anthropic-specific (less portable)
- Newer SDK, smaller community
- Requires Anthropic API access

### Confirmation

- 80%+ pass rate on SWE-bench-style test set
- p95 task completion < 30 minutes
- Sub-agent overhead < 20% of total runtime

## Pros and cons of the options

| Option | Long-horizon | Self-reflection | Computer use | Multi-agent |
|---|---|---|---|---|
| **Claude Agent SDK** | ✅ Native | ✅ Native | ✅ Native | ✅ Sub-agents |
| LangGraph | ⚠️ Manual | ⚠️ Manual | ❌ No | ✅ Graph |
| CrewAI | ❌ Not native | ❌ No | ❌ No | ✅ Yes |
| OpenAI Agents | ⚠️ Manual | ❌ No | ❌ No | ✅ Yes |

## References

- [Claude Agent SDK](https://docs.claude.com/en/docs/agents-and-tools/claude-code/overview)
- [SWE-bench](https://www.swebench.com/)
