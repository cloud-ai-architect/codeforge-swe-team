"""Lambda handler for the Coder stage."""

from __future__ import annotations

from src.agents.codeforge import CoderAgent
from src.lambdas._base import run_stage


def handler(event: dict, context: object) -> dict:
    return run_stage(
        event,
        required=["task"],
        fn=lambda d: CoderAgent().run(d["task"], d.get("files"), d.get("plan")),
    )
