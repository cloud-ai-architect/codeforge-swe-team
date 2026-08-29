"""Tests for the sandbox client.

These cover the parts that run without AWS: configuration detection, input
validation, and the prompt-rendering helper. Execution itself is exercised
against a real Fargate task rather than mocked, because what is being
tested there is the isolation, which a mock cannot show.
"""

from __future__ import annotations

import pytest

from src.agents.codeforge import _render_files
from src.sandbox import SandboxError, SandboxNotConfiguredError, is_configured, run


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
