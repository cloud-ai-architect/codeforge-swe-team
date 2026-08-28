"""Issue Triage Agent — fetches and understands the GitHub issue."""

from __future__ import annotations

import json
from typing import Any

from src.common import BaseAgent, CodeTask


ISSUE_TRIAGE_PROMPT = """You are an expert software engineer doing issue triage.

You will receive a GitHub issue. Your job is to understand it and produce a structured analysis:

1. **Summary** (1-2 sentences): What is the user asking for?
2. **Type**: bug | feature | refactor | docs | question
3. **Acceptance Criteria**: What does "done" look like?
4. **Affected Areas**: Which files/modules likely need changes?
5. **Complexity**: trivial | small | medium | large
6. **Risk**: low | medium | high (what could break?)
7. **Open Questions**: What needs clarification before coding?

Respond in JSON."""


class IssueTriageAgent(BaseAgent):
    NAME = "issue_triage"

    def handle(self, task: CodeTask) -> CodeTask:
        prompt = f"""Issue title: {task.issue_title}

Issue body:
{task.issue_body}

Repo: {task.repo_full_name}
Issue number: #{task.issue_number}

Analyze this issue per the schema above."""
        result = self.invoke_claude(
            system=ISSUE_TRIAGE_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        # Parse JSON (may need cleanup)
        text = result.strip().strip("`").removeprefix("json").strip()
        try:
            triage = json.loads(text)
        except json.JSONDecodeError:
            triage = {"summary": result, "raw": True}

        task.artifacts["triage"] = triage
        return task
