"""Sandbox tools — manage the Fargate execution environment."""

from __future__ import annotations

import json
from typing import Any

import boto3


def run_in_sandbox(
    task_id: str,
    repo: str,
    branch: str,
    prompt: str,
    model: str = "anthropic.claude-sonnet-4-5-20250929-v1:0",
    timeout: int = 600,
) -> dict[str, Any]:
    """Run a Claude Agent SDK task in a Fargate Spot sandbox.

    The sandbox:
    - Clones the repo at the given branch
    - Runs `claude --prompt <prompt>` in the workdir
    - Captures git diff and any test output
    - Writes result to S3
    """
    ecs = boto3.client("ecs", region_name="ap-south-1")
    s3 = boto3.client("s3", region_name="ap-south-1")

    bucket = f"{repo.replace('/', '-')}-sandbox"
    prefix = f"runs/{task_id}"

    # Stage input
    s3.put_object(
        Bucket=bucket,
        Key=f"{prefix}/input.json",
        Body=json.dumps(
            {
                "task_id": task_id,
                "repo": repo,
                "branch": branch,
                "prompt": prompt,
                "model": model,
                "timeout": timeout,
            }
        ),
    )

    # Start task
    response = ecs.run_task(
        cluster="codeforge-sandbox",
        taskDefinition="codeforge-sandbox:1",
        launchType="FARGATE_SPOT",
        overrides={
            "containerOverrides": [
                {
                    "name": "sandbox",
                    "environment": [
                        {
                            "name": "TASK_INPUT_S3_URI",
                            "value": f"s3://{bucket}/{prefix}/input.json",
                        },
                        {"name": "RESULT_S3_BUCKET", "value": bucket},
                        {"name": "RESULT_S3_KEY", "value": f"{prefix}/result.json"},
                    ],
                }
            ],
        },
    )

    return {"task_arn": response["tasks"][0]["taskArn"]}
