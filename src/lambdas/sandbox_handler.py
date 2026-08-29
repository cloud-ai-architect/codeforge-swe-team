"""Lambda handler for the Sandbox stage.

This handler is a client, not an executor: it starts an isolated Fargate
task and reports the result. The code never runs inside this Lambda.
"""

from __future__ import annotations

from src.lambdas._base import respond, run_stage
from src.sandbox import SandboxNotConfigured, is_configured, run


def _execute(data: dict) -> dict:
    return run(
        data["code"],
        language=data.get("language", "python"),
        timeout=data.get("timeout"),
    )


def handler(event: dict, context: object) -> dict:
    if not is_configured():
        return respond(503, {
            "error": "SANDBOX_NOT_CONFIGURED",
            "message": "The execution sandbox is not provisioned in this environment.",
        })
    return run_stage(event, required=["code"], fn=_execute)
