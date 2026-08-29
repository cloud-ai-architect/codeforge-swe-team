"""Isolated execution of model-authored code.

Running code a model just wrote is the one part of this system that cannot
live in the Lambda that orchestrates it. Lambda gives you a shared execution
environment with outbound network access and a writable /tmp; that is the
wrong boundary for arbitrary generated code.

Execution therefore runs as an ECS Fargate task with:

  - no route to the internet (the subnet has no NAT and no internet
                        gateway; egress is limited to HTTPS to the ECR and
                        CloudWatch VPC endpoints, which the ECS agent needs
                        to pull the image and ship logs, and to the S3
                        prefix list that carries the image layers)
  - read-only root filesystem, with a small tmpfs for scratch
  - a non-root user
  - a hard wall-clock timeout enforced by the caller, and a task-level
    stop timeout as a backstop
  - no task role beyond writing its own logs, so even if code escapes the
    interpreter it holds no AWS permissions

The Lambda side is only a client: it starts the task, waits, and reads the
result from CloudWatch Logs. It never executes the payload itself.
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

import boto3

REGION = os.environ.get("AWS_REGION", "ap-south-1")

CLUSTER = os.environ.get("SANDBOX_CLUSTER", "")
TASK_DEFINITION = os.environ.get("SANDBOX_TASK_DEFINITION", "")
SUBNETS = [s for s in os.environ.get("SANDBOX_SUBNETS", "").split(",") if s]
SECURITY_GROUPS = [s for s in os.environ.get("SANDBOX_SECURITY_GROUPS", "").split(",") if s]
LOG_GROUP = os.environ.get("SANDBOX_LOG_GROUP", "")

# Wall-clock ceiling for a single run. The Fargate task also has its own stop
# timeout; this is the caller-side bound so a wedged task cannot hold the
# Lambda open until its own timeout.
MAX_WAIT_SECONDS = int(os.environ.get("SANDBOX_MAX_WAIT", "240"))
POLL_INTERVAL = 3


class SandboxError(Exception):
    """The sandbox could not be started, or did not return a usable result."""


class SandboxNotConfiguredError(SandboxError):
    """Sandbox environment variables are absent."""


def is_configured() -> bool:
    return bool(CLUSTER and TASK_DEFINITION and SUBNETS)


def run(code: str, language: str = "python", timeout: int | None = None) -> dict[str, Any]:
    """Execute `code` in an isolated Fargate task and return its result.

    The code is passed base64-encoded through the container command rather
    than written to a shared volume, so nothing is persisted between runs.
    """
    if language != "python":
        raise SandboxError(f"unsupported language: {language}")
    if not is_configured():
        raise SandboxNotConfiguredError(
            "sandbox is not configured; set SANDBOX_CLUSTER, "
            "SANDBOX_TASK_DEFINITION and SANDBOX_SUBNETS"
        )

    deadline = time.time() + min(timeout or MAX_WAIT_SECONDS, MAX_WAIT_SECONDS)
    ecs = boto3.client("ecs", region_name=REGION)
    encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")

    started = ecs.run_task(
        cluster=CLUSTER,
        taskDefinition=TASK_DEFINITION,
        launchType="FARGATE",
        count=1,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": SUBNETS,
                "securityGroups": SECURITY_GROUPS,
                # No public IP: combined with a subnet that has no NAT, the
                # task has no route off the VPC.
                "assignPublicIp": "DISABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "runner",
                    "command": [
                        "python",
                        "-c",
                        "import base64,sys;exec(base64.b64decode(sys.argv[1]))",
                        encoded,
                    ],
                }
            ]
        },
    )

    failures = started.get("failures") or []
    if failures:
        raise SandboxError(f"could not start sandbox task: {json.dumps(failures)}")

    task_arn = started["tasks"][0]["taskArn"]
    task_id = task_arn.rsplit("/", 1)[-1]

    exit_code, reason = _wait(ecs, task_arn, deadline)
    logs = _fetch_logs(task_id) if LOG_GROUP else []

    return {
        "task_id": task_id,
        "exit_code": exit_code,
        "timed_out": exit_code is None,
        "stopped_reason": reason,
        "output": "\n".join(logs)[:20000],
        "isolation": {
            "internet_route": False,
            "egress": "ECR/CloudWatch VPC endpoints and S3 prefix list only",
            "root_filesystem": "read-only",
            "user": "non-root",
            "task_role_permissions": "none",
        },
    }


def _wait(ecs: Any, task_arn: str, deadline: float) -> tuple[int | None, str]:
    """Poll until the task stops or the deadline passes."""
    while time.time() < deadline:
        desc = ecs.describe_tasks(cluster=CLUSTER, tasks=[task_arn])
        tasks = desc.get("tasks") or []
        if not tasks:
            raise SandboxError("sandbox task disappeared before completing")

        task = tasks[0]
        if task.get("lastStatus") == "STOPPED":
            containers = task.get("containers") or [{}]
            return containers[0].get("exitCode"), task.get("stoppedReason", "")
        time.sleep(POLL_INTERVAL)

    # Deadline hit: stop the task so it cannot keep running unattended.
    try:
        ecs.stop_task(cluster=CLUSTER, task=task_arn, reason="caller timeout")
    except Exception as exc:  # noqa: BLE001 - best effort; result is already a timeout
        print(f"could not stop timed-out sandbox task: {exc!r}")
    return None, f"timed out after {MAX_WAIT_SECONDS}s"


def _fetch_logs(task_id: str) -> list[str]:
    """Read the task's stdout from CloudWatch Logs."""
    client = boto3.client("logs", region_name=REGION)
    stream = f"sandbox/runner/{task_id}"
    try:
        resp = client.get_log_events(
            logGroupName=LOG_GROUP,
            logStreamName=stream,
            startFromHead=True,
            limit=1000,
        )
    except client.exceptions.ResourceNotFoundException:
        # The task can stop before its log stream is created, e.g. if the
        # image failed to pull. An empty result is more useful than an error.
        return []
    return [e["message"] for e in resp.get("events", [])]


__all__ = ["SandboxError", "SandboxNotConfiguredError", "is_configured", "run"]
