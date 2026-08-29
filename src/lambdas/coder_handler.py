"""Lambda handler for the Coder stage."""

from __future__ import annotations

from typing import Any

from src.agents.codeforge import CoderAgent
from src.lambdas._base import run_stage


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    return run_stage(
        event,
        required=["task"],
        fn=lambda d: CoderAgent().run(d["task"], d.get("files"), d.get("plan")),
    )
