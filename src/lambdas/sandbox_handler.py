"""Lambda handler for the Sandbox stage.

This handler is a client, not an executor: it starts an isolated Fargate task
and reports on it. The code never runs inside this Lambda.

The API is asynchronous. A cold Fargate task takes 30-60 seconds to pull its
image and run, and API Gateway cuts an integration off at 30, so waiting
inline returned 503 to the caller even when the task had completed correctly.
POST /v1/run starts a task and returns its id; POST /v1/run with that id
reports whether it has finished and, once it has, its output.
"""

from __future__ import annotations

from typing import Any

from src.lambdas._base import respond, run_stage
from src.sandbox import SandboxError, collect, is_configured, start


def _dispatch(data: dict[str, Any]) -> dict[str, Any]:
    """Start a run, or report on one already started.

    One route rather than two: a caller that has a task id is asking about
    that task, and a caller with code is asking to run it.
    """
    task_id = data.get("task_id") or data.get("run_id")
    if task_id:
        return collect(str(task_id))

    return {
        "task_id": start(str(data["code"]), language=data.get("language", "python")),
        "status": "started",
        "poll": "POST the returned task_id back to this endpoint to collect the result",
    }


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    if not is_configured():
        return respond(
            503,
            {
                "error": "SANDBOX_NOT_CONFIGURED",
                "message": "The execution sandbox is not provisioned in this environment.",
            },
        )

    # Either input is sufficient, so neither can be declared required: the
    # check is that at least one is present.
    from src.lambdas._base import parse_event

    data = parse_event(event)
    if not data.get("code") and not (data.get("task_id") or data.get("run_id")):
        return respond(
            400,
            {
                "error": "MISSING_PARAMETERS",
                "message": "required: code (to start a run) or task_id (to collect one)",
            },
        )

    try:
        return run_stage(event, required=[], fn=_dispatch)
    except SandboxError as exc:
        return respond(502, {"error": "SANDBOX_ERROR", "message": str(exc)})
