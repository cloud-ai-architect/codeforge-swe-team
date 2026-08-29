"""Lambda handler for the Planner stage."""

from __future__ import annotations

from typing import Any

from src.agents.codeforge import PlannerAgent
from src.lambdas._base import run_stage


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    return run_stage(
        event,
        required=["issue"],
        fn=lambda d: PlannerAgent().run(d["issue"], d.get("files")),
    )
