"""CodeForge software engineering agents.

Four specialists behind an orchestrator:

    Planner   break an issue into an ordered, reviewable plan  (standard tier)
    Coder     produce a unified diff against the given files   (standard tier)
    Reviewer  review a diff for correctness and risk           (standard tier)
    Sandbox   execute the produced code in isolation           (no model)

Sandbox is the reason this project exists in a portfolio that is otherwise
Lambda request/response: running model-authored code needs a boundary that a
Lambda cannot give you. Execution happens in a Fargate task with no network
egress, a read-only root filesystem, a hard timeout and a non-root user, so
generated code that tries to reach the network or persist anything simply
fails. See src/sandbox.py.

The consistent constraint across the model-driven agents is that they work
only from the supplied files. An agent that invents a function signature
produces a diff that will not apply, so each is required to state what it
could not see rather than assume it.
"""

from __future__ import annotations

from typing import Any

from src.common import MODEL_FAST, MODEL_STANDARD, BaseAgent


class PlannerAgent(BaseAgent):
    """Turn an issue into an ordered implementation plan."""

    NAME = "planner"
    MODEL = MODEL_STANDARD
    SYSTEM_PROMPT = (
        "You plan code changes for a software engineer.\n"
        "Break the issue into ordered steps, each small enough to review on "
        "its own. Reference only files you were given; if the change needs a "
        "file you cannot see, list it under files_needed rather than "
        "guessing at its contents.\n"
        "Call out anything that would change public behaviour.\n"
        "Respond with JSON only:\n"
        '{"summary": "one sentence",\n'
        ' "steps": [{"n": 1, "action": "...", "files": ["..."],'
        ' "rationale": "..."}],\n'
        ' "files_needed": ["files required but not supplied"],\n'
        ' "breaking_changes": ["..."],\n'
        ' "test_strategy": "how the change should be verified"}'
    )

    def handle(self, issue: str, files: dict[str, str] | None = None) -> dict[str, Any]:
        prompt = "Issue:\n%s\n" % issue
        if files:
            prompt += "\nRepository files:\n" + _render_files(files)
        return self.invoke_json(prompt, max_tokens=3000)


class CoderAgent(BaseAgent):
    """Produce a unified diff implementing a plan."""

    NAME = "coder"
    MODEL = MODEL_STANDARD
    SYSTEM_PROMPT = (
        "You write code changes as a unified diff.\n"
        "Work only from the supplied file contents. Do not invent functions, "
        "imports or signatures that are not shown -- a diff built on a guessed "
        "signature will not apply.\n"
        "Match the surrounding style: if the file has no type hints, do not "
        "add them; if it uses a particular error type, use that one.\n"
        "Respond with JSON only:\n"
        '{"diff": "unified diff, or empty string if no change is warranted",\n'
        ' "files_changed": ["..."],\n'
        ' "explanation": "what the change does and why",\n'
        ' "assumptions": ["anything you had to assume"],\n'
        ' "tests_to_add": ["..."]}'
    )

    def handle(
        self,
        task: str,
        files: dict[str, str] | None = None,
        plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import json

        prompt = "Task:\n%s\n" % task
        if plan:
            prompt += "\nPlan:\n%s\n" % json.dumps(plan, indent=1)[:2500]
        if files:
            prompt += "\nRepository files:\n" + _render_files(files)
        return self.invoke_json(prompt, max_tokens=4000)


class ReviewerAgent(BaseAgent):
    """Review a diff for correctness and risk."""

    NAME = "reviewer"
    MODEL = MODEL_STANDARD
    SYSTEM_PROMPT = (
        "You review a code diff the way a careful colleague would.\n"
        "Report only defects you can point at in the diff. Do not pad the "
        "review with style preferences or speculation; if the change looks "
        "correct, say so.\n"
        "For each finding give the concrete failure: the input or state that "
        "produces the wrong result.\n"
        "Respond with JSON only:\n"
        '{"verdict": "approve|request_changes|needs_discussion",\n'
        ' "findings": [{"severity": "high|medium|low", "file": "...",\n'
        '               "issue": "...", "failure_case": "input -> wrong output",\n'
        '               "suggestion": "..."}],\n'
        ' "missing_tests": ["..."],\n'
        ' "summary": "one or two sentences"}'
    )

    def handle(self, diff: str, context: str = "") -> dict[str, Any]:
        prompt = "Diff under review:\n%s\n" % diff
        if context:
            prompt += "\nContext:\n%s" % context
        return self.invoke_json(prompt, max_tokens=3000)


class OrchestratorAgent(BaseAgent):
    """Route an engineering request to the right specialist."""

    NAME = "orchestrator"
    MODEL = MODEL_FAST
    SYSTEM_PROMPT = (
        "You route software engineering requests to one specialist agent.\n"
        "Options:\n"
        "  planner  - breaking an issue into an implementation plan\n"
        "  coder    - writing the change as a diff\n"
        "  reviewer - reviewing an existing diff\n"
        "  sandbox  - executing code to see what it does\n"
        "Respond with JSON only:\n"
        '{"agent": "planner|coder|reviewer|sandbox", "reason": "one sentence"}'
    )

    VALID = {"planner", "coder", "reviewer", "sandbox"}

    def handle(self, request: str) -> dict[str, Any]:
        result = self.invoke_json("Request:\n%s" % request)
        if result.get("agent") not in self.VALID:
            # Planner is the safe default: it is the only agent that produces
            # something useful without a diff or code already in hand.
            result = {
                "agent": "planner",
                "reason": "router returned an unknown agent; defaulting to planner",
            }
        return result


def _render_files(files: dict[str, str], limit: int = 6000) -> str:
    """Render a file map for the prompt, truncating very large files."""
    parts = []
    for name, body in files.items():
        text = body if len(body) <= limit else body[:limit] + "\n... (truncated)"
        parts.append("--- %s ---\n%s" % (name, text))
    return "\n\n".join(parts)


AGENTS: dict[str, type[BaseAgent]] = {
    "planner": PlannerAgent,
    "coder": CoderAgent,
    "reviewer": ReviewerAgent,
    "orchestrator": OrchestratorAgent,
}

__all__ = ["AGENTS", "CoderAgent", "OrchestratorAgent", "PlannerAgent", "ReviewerAgent"]
