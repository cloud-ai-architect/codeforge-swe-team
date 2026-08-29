"""Lambda handler for the Reviewer stage."""

from __future__ import annotations

from typing import Any

from src.agents.codeforge import ReviewerAgent
from src.lambdas._base import run_stage


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    return run_stage(
        event,
        required=["diff"],
        fn=lambda d: ReviewerAgent().run(d["diff"], d.get("context", "")),
    )
