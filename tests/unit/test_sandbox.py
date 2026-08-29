"""Tests for the sandbox client.

These cover the parts that run without AWS: configuration detection, input
validation, and the prompt-rendering helper. Execution itself is exercised
against a real Fargate task rather than mocked, because what is being
tested there is the isolation, which a mock cannot show.
"""

from __future__ import annotations

import pytest

from src.agents.codeforge import _render_files
from src.sandbox import SandboxError, SandboxNotConfiguredError, run


class TestConfiguration:
    def test_reports_unconfigured_when_env_absent(self, monkeypatch):
        """The module reads env at import, so this asserts the accessor
        rather than re-importing."""
        import src.sandbox as sandbox

        monkeypatch.setattr(sandbox, "CLUSTER", "")
        assert not sandbox.is_configured()

    def test_reports_configured_when_all_present(self, monkeypatch):
        import src.sandbox as sandbox

        monkeypatch.setattr(sandbox, "CLUSTER", "c")
        monkeypatch.setattr(sandbox, "TASK_DEFINITION", "t")
        monkeypatch.setattr(sandbox, "SUBNETS", ["subnet-1"])
        assert sandbox.is_configured()

    def test_partial_configuration_is_not_configured(self, monkeypatch):
        import src.sandbox as sandbox

        monkeypatch.setattr(sandbox, "CLUSTER", "c")
        monkeypatch.setattr(sandbox, "TASK_DEFINITION", "")
        assert not sandbox.is_configured()


class TestRunValidation:
    def test_unsupported_language_rejected_before_any_aws_call(self):
        with pytest.raises(SandboxError):
            run("print(1)", language="ruby")

    def test_unconfigured_raises_a_distinct_error(self, monkeypatch):
        """Callers map this to 503 rather than 500: an unprovisioned
        sandbox is a deployment state, not a failure."""
        import src.sandbox as sandbox

        monkeypatch.setattr(sandbox, "CLUSTER", "")
        with pytest.raises(SandboxNotConfiguredError):
            sandbox.run("print(1)")

    def test_not_configured_error_is_a_sandbox_error(self):
        assert issubclass(SandboxNotConfiguredError, SandboxError)


class TestRenderFiles:
    def test_includes_each_filename(self):
        out = _render_files({"a.py": "x = 1", "b.py": "y = 2"})
        assert "a.py" in out and "b.py" in out

    def test_truncates_large_files(self):
        out = _render_files({"big.py": "z" * 9000}, limit=100)
        assert "truncated" in out
        assert len(out) < 1000

    def test_small_files_are_not_truncated(self):
        out = _render_files({"s.py": "print(1)"}, limit=100)
        assert "truncated" not in out

    def test_empty_map_renders_empty(self):
        assert _render_files({}) == ""


class FakeEcs:
    """Enough of the ECS client for start() and collect()."""

    def __init__(self, task=None, run_failures=None):
        self._task = task
        self._run_failures = run_failures or []
        self.run_task_calls = []

    def run_task(self, **kwargs):
        self.run_task_calls.append(kwargs)
        if self._run_failures:
            return {"failures": self._run_failures, "tasks": []}
        return {
            "failures": [],
            "tasks": [{"taskArn": "arn:aws:ecs:ap-south-1:1:task/cluster/abc123"}],
        }

    def describe_tasks(self, **kwargs):
        return {"tasks": [self._task] if self._task else []}


def _configure(monkeypatch, ecs):
    import boto3

    import src.sandbox as sandbox

    monkeypatch.setattr(sandbox, "CLUSTER", "cluster")
    monkeypatch.setattr(sandbox, "TASK_DEFINITION", "taskdef")
    monkeypatch.setattr(sandbox, "SUBNETS", ["subnet-1"])
    monkeypatch.setattr(sandbox, "LOG_GROUP", "")
    monkeypatch.setattr(boto3, "client", lambda _svc, **_kw: ecs)
    return sandbox


class TestStart:
    def test_returns_the_task_id_not_the_arn(self, monkeypatch):
        ecs = FakeEcs()
        sandbox = _configure(monkeypatch, ecs)
        assert sandbox.start("print(1)") == "abc123"

    def test_task_has_no_public_ip(self, monkeypatch):
        # Combined with a subnet that has no NAT, this is what leaves the
        # task with no route off the VPC. If it ever flips to ENABLED the
        # isolation claim in the response becomes false.
        ecs = FakeEcs()
        sandbox = _configure(monkeypatch, ecs)
        sandbox.start("print(1)")
        net = ecs.run_task_calls[0]["networkConfiguration"]["awsvpcConfiguration"]
        assert net["assignPublicIp"] == "DISABLED"

    def test_code_is_passed_base64_encoded(self, monkeypatch):
        import base64

        ecs = FakeEcs()
        sandbox = _configure(monkeypatch, ecs)
        sandbox.start("print('hi')")
        command = ecs.run_task_calls[0]["overrides"]["containerOverrides"][0]["command"]
        assert base64.b64decode(command[-1]).decode() == "print('hi')"

    def test_rejects_a_language_it_cannot_run(self, monkeypatch):
        sandbox = _configure(monkeypatch, FakeEcs())
        with pytest.raises(SandboxError, match="unsupported language"):
            sandbox.start("puts 1", language="ruby")

    def test_start_failure_is_reported(self, monkeypatch):
        ecs = FakeEcs(run_failures=[{"reason": "capacity"}])
        sandbox = _configure(monkeypatch, ecs)
        with pytest.raises(SandboxError, match="could not start"):
            sandbox.start("print(1)")

    def test_unconfigured_start_raises(self, monkeypatch):
        import src.sandbox as sandbox

        monkeypatch.setattr(sandbox, "CLUSTER", "")
        with pytest.raises(SandboxNotConfiguredError):
            sandbox.start("print(1)")


class TestCollect:
    def test_running_task_reports_running(self, monkeypatch):
        sandbox = _configure(monkeypatch, FakeEcs(task={"lastStatus": "PENDING"}))
        result = sandbox.collect("abc123")
        assert result["status"] == "running"
        assert result["last_status"] == "PENDING"
        # No exit code is invented while the task is still going.
        assert "exit_code" not in result

    def test_stopped_task_reports_the_exit_code(self, monkeypatch):
        task = {
            "lastStatus": "STOPPED",
            "stoppedReason": "Essential container exited",
            "containers": [{"exitCode": 0}],
        }
        sandbox = _configure(monkeypatch, FakeEcs(task=task))
        result = sandbox.collect("abc123")
        assert result["status"] == "complete"
        assert result["exit_code"] == 0
        assert result["isolation"]["internet_route"] is False

    def test_nonzero_exit_is_preserved(self, monkeypatch):
        task = {"lastStatus": "STOPPED", "containers": [{"exitCode": 1}]}
        sandbox = _configure(monkeypatch, FakeEcs(task=task))
        assert sandbox.collect("abc123")["exit_code"] == 1

    def test_unknown_task_raises(self, monkeypatch):
        sandbox = _configure(monkeypatch, FakeEcs(task=None))
        with pytest.raises(SandboxError, match="no such sandbox task"):
            sandbox.collect("nope")
