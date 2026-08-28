"""Planner Agent — decomposes the issue into subtasks."""

from __future__ import annotations

import json

from src.common import BaseAgent, CodeTask


PLANNER_PROMPT = """You are a software architect planning the implementation of a feature or fix.

Given the issue and triage analysis, produce a step-by-step plan.

Output a JSON array of subtasks:
[
  {{
    "id": 1,
    "title": "...",
    "description": "...",
    "files_to_modify": ["path/to/file.py", ...],
    "tests_to_add": ["tests/test_x.py", ...],
    "estimated_minutes": 10,
    "depends_on": []
  }},
  ...
]

Keep it to 3-7 subtasks. Prefer fewer, larger subtasks over many tiny ones."""


class PlannerAgent(BaseAgent):
    NAME = "planner"

    def handle(self, task: CodeTask) -> CodeTask:
        triage = task.artifacts.get("triage", {})
        prompt = f"""Issue: {task.issue_title}
Description: {task.issue_body}

Triage: {json.dumps(triage, indent=2)}

Plan the implementation."""
        result = self.invoke_claude(
            system=PLANNER_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            text = result.strip().strip("`").removeprefix("json").strip()
            plan = json.loads(text)
        except json.JSONDecodeError:
            plan = [{"id": 1, "title": "Implement", "description": result, "files_to_modify": [], "tests_to_add": []}]
        task.plan = json.dumps(plan, indent=2)
        task.artifacts["plan"] = plan
        return task
