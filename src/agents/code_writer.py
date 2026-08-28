"""Code Writer Agent — implements the changes in a sandboxed Fargate task."""

from __future__ import annotations

import json
import time
import uuid

import boto3

from src.common import BaseAgent, CodeTask


CODE_WRITER_PROMPT = """You are a senior software engineer. You will be given a plan and must implement it.

Plan:
{plan}

Working directory: /workspace/repo (already cloned)
Branch name: codeforge/{task_id}

For each subtask:
1. Read the relevant files
2. Make the minimum change to satisfy the requirement
3. Follow the project's existing code style
4. Add tests if the subtask includes "tests_to_add"

When done, output a unified diff of all your changes.

Use the bash tool to run commands. Use the file_editor to read/write files.

IMPORTANT: Your output must end with a diff in unified format starting with 'diff --git'."""


class CodeWriterAgent(BaseAgent):
    NAME = "code_writer"

    def __init__(self) -> None:
        super().__init__()
        self.ecs = None
        self.s3 = None
        self.log = self.log.bind(agent=self.NAME)

    def setup(self) -> None:
        self.ecs = boto3.client("ecs", region_name="ap-south-1")
        self.s3 = boto3.client("s3", region_name="ap-south-1")

    def handle(self, task: CodeTask) -> CodeTask:
        # Start Fargate sandbox task
        sandbox_bucket = f"{task.repo_full_name.replace('/', '-')}-sandbox"
        sandbox_prefix = f"runs/{task.task_id}"

        prompt = CODE_WRITER_PROMPT.format(
            plan=task.plan,
            task_id=task.task_id,
        )

        # Start the sandbox task (input via env vars or S3)
        run_input = {
            "task_id": task.task_id,
            "repo": task.repo_full_name,
            "branch": f"codeforge/{task.task_id}",
            "prompt": prompt,
            "model": "anthropic.claude-sonnet-4-5-20250929-v1:0",
        }
        input_key = f"{sand}/input.json"
        self.s3.put_object(Bucket=sandbox_bucket, Key=input_key, Body=json.dumps(run_input))

        response = self.ecs.run_task(
            cluster="codeforge-sandbox",
            taskDefinition="codeforge-sandbox:1",
            launchType="FARGATE_SPOT",
            overrides={
                "containerOverrides": [{
                    "name": "sandbox",
                    "environment": [
                        {"name": "TASK_INPUT_S3_URI", "value": f"s3://{sandbox_bucket}/{input_key}"},
                        {"name": "RESULT_S3_BUCKET", "value": sandbox_bucket},
                        {"name": "RESULT_S3_KEY", "value": f"{sand}/result.json"},
                    ],
                }],
            },
        )
        task_arn = response["tasks"][0]["taskArn"]

        # Wait for completion
        result = self._wait_for_sandbox(task_arn, sandbox_bucket, sand)

        task.artifacts["code_writer"] = result
        return task

    def _wait_for_sandbox(self, task_arn: str, bucket: str, prefix: str, timeout: int = 600) -> dict:
        """Wait for the Fargate sandbox task to finish."""
        start = time.time()
        while time.time() - start < timeout:
            response = self.ecs.describe_tasks(cluster="codeforge-sandbox", tasks=[task_arn])
            status = response["tasks"][0]["lastStatus"]
            if status in ("STOPPED", "DEAD"):
                # Read result
                try:
                    obj = self.s3.get_object(Bucket=bucket, Key=f"{prefix}/result.json")
                    return json.loads(obj["Body"].read().decode("utf-8"))
                except Exception:
                    return {"error": "Task stopped but no result"}
            time.sleep(3)
        return {"error": "Task timeout"}
