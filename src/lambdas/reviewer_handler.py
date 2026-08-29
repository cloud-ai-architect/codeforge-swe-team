"""Lambda handler for the Reviewer stage."""

from __future__ import annotations

from src.agents.codeforge import ReviewerAgent
from src.lambdas._base import run_stage


def handler(event: dict, context: object) -> dict:
    return run_stage(
        event,
        required=["diff"],
        fn=lambda d: ReviewerAgent().run(d["diff"], d.get("context", "")),
    )
