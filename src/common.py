"""Common base classes for CodeForge agents."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, ClassVar

import structlog

logger = structlog.get_logger()


@dataclass
class CodeForgeError(Exception):
    """Base exception."""
    message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class SandboxError(CodeForgeError):
    """Sandbox execution failed."""


@dataclass
class GitHubError(CodeForgeError):
    """GitHub API call failed."""


@dataclass
class AgentError(CodeForgeError):
    """Agent failed to produce output."""


@dataclass
class CodeTask:
    """A unit of work for the CodeForge pipeline."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issue_url: str = ""
    repo_full_name: str = ""
    issue_number: int = 0
    issue_title: str = ""
    issue_body: str = ""
    plan: str = ""
    current_attempt: int = 0
    max_attempts: int = 3
    status: str = "pending"  # pending | planning | coding | testing | reviewing | pr_open | ci_running | ci_failed | done | failed
    artifacts: dict[str, Any] = field(default_factory=dict)  # patch_url, test_output, pr_url, etc.
    started_at: float = 0.0
    completed_at: float = 0.0
    cumulative_cost_usd: float = 0.0


class BaseAgent:
    """Base class for all CodeForge agents."""

    NAME: ClassVar[str] = ""

    def __init__(self) -> None:
        if not self.NAME:
            raise ValueError(f"{type(self).__name__} must set NAME")
        self.log = logger.bind(agent=self.NAME)
        self.bedrock = None
        self.s3 = None
        self.dynamodb = None
        self._setup_done = False

    def setup(self) -> None:
        pass

    def ensure_setup(self) -> None:
        if self._setup_done:
            return
        import boto3
        self.bedrock = boto3.client("bedrock-runtime", region_name="ap-south-1")
        self.s3 = boto3.client("s3", region_name="ap-south-1")
        self.dynamodb = boto3.client("dynamodb", region_name="ap-south-1")
        self.setup()
        self._setup_done = True

    def invoke_claude(
        self,
        system: str,
        messages: list[dict[str, Any]],
        model: str = "anthropic.claude-sonnet-4-5-20250929-v1:0",
        max_tokens: int = 4096,
    ) -> str:
        self.ensure_setup()
        import json
        response = self.bedrock.invoke_model(
            modelId=model,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "system": system,
                "messages": messages,
            }),
        )
        return json.loads(response["body"].read())["content"][0]["text"]

    def reflect(self, task: CodeTask, error: str) -> str:
        """Self-reflection after a failure: why did this fail, what to try next."""
        prompt = f"""You are a coding agent. A previous attempt failed.

Task: {task.issue_title}
Description: {task.issue_body}
Previous attempt: attempt #{task.current_attempt}
Error: {error}

Reflect:
1. WHY did this fail? (be specific)
2. What is the most likely root cause?
3. What would you try DIFFERENTLY next time?

Respond concisely."""
        return self.invoke_claude(
            system="You are an expert software engineer. Be specific and analytical.",
            messages=[{"role": "user", "content": prompt}],
        )

    def run(self, task: CodeTask) -> CodeTask:
        """Main entry point. Subclasses implement handle()."""
        self.ensure_setup()
        start = time.perf_counter()
        try:
            task.status = self.NAME
            task.current_attempt += 1
            self.log.info("agent.start", task_id=task.task_id, attempt=task.current_attempt)
            result = self.handle(task)
            task.completed_at = time.perf_counter()
            self.log.info("agent.success", task_id=task.task_id, duration_ms=int((task.completed_at - start) * 1000))
            return result
        except Exception as exc:
            task.completed_at = time.perf_counter()
            self.log.error("agent.error", task_id=task.task_id, error=str(exc))
            task.artifacts["last_error"] = str(exc)
            task.artifacts["last_reflection"] = self.reflect(task, str(exc))
            task.status = f"{self.NAME}_failed"
            raise

    def handle(self, task: CodeTask) -> CodeTask:  # noqa: ARG002
        raise NotImplementedError


__all__ = [
    "AgentError",
    "BaseAgent",
    "CodeForgeError",
    "CodeTask",
    "GitHubError",
    "SandboxError",
]
