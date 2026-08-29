"""Unit tests for CodeForge Lambda plumbing and routing."""

from __future__ import annotations

import json

import pytest

from src.common import BaseAgent, CodeForgeError, ModelError
from src.lambdas._base import parse_event, respond, run_stage


class TestParseEvent:
    def test_direct_invocation(self):
        assert parse_event({"issue": "x"})["issue"] == "x"

    def test_api_gateway_string_body(self):
        ev = {"body": json.dumps({"issue": "x"})}
        assert parse_event(ev)["issue"] == "x"

    def test_api_gateway_dict_body(self):
        assert parse_event({"body": {"issue": "x"}})["issue"] == "x"

    def test_malformed_json_body_does_not_raise(self):
        assert parse_event({"body": "{not json"}) == {}

    def test_query_string_parameters(self):
        ev = {"queryStringParameters": {"issue": "x"}}
        assert parse_event(ev)["issue"] == "x"

    def test_non_dict_event(self):
        assert parse_event(None) == {}


class TestRunStage:
    def test_missing_parameter_returns_400(self):
        r = run_stage({}, ["issue"], lambda d: "never")
        assert r["statusCode"] == 400
        assert "issue" in json.loads(r["body"])["message"]

    def test_lists_every_missing_parameter(self):
        r = run_stage({}, ["issue", "files"], lambda d: "never")
        msg = json.loads(r["body"])["message"]
        assert "issue" in msg and "files" in msg

    def test_empty_string_counts_as_missing(self):
        r = run_stage({"issue": ""}, ["issue"], lambda d: "never")
        assert r["statusCode"] == 400

    def test_success_wraps_result(self):
        r = run_stage({"issue": "x"}, ["issue"], lambda d: {"ok": True})
        assert r["statusCode"] == 200
        assert json.loads(r["body"])["result"] == {"ok": True}

    def test_model_error_maps_to_502(self):
        def boom(d):
            raise ModelError("bedrock unavailable")

        r = run_stage({"issue": "x"}, ["issue"], boom)
        assert r["statusCode"] == 502
        assert json.loads(r["body"])["error"] == "ModelError"

    def test_unexpected_error_maps_to_500(self):
        def boom(d):
            raise RuntimeError("kaboom")

        r = run_stage({"issue": "x"}, ["issue"], boom)
        assert r["statusCode"] == 500

    def test_response_is_json_serialisable(self):
        r = respond(200, {"a": 1})
        assert json.loads(r["body"]) == {"a": 1}
        assert r["headers"]["Content-Type"] == "application/json"


class StubAgent(BaseAgent):
    """Agent with the model call stubbed out."""

    NAME = "stub"

    def __init__(self, reply):
        super().__init__()
        self._reply = reply
        self._setup_done = True

    def invoke(self, prompt, **kwargs):
        return self._reply


class TestInvokeJson:
    def test_parses_bare_json(self):
        assert StubAgent('{"a": 1}').invoke_json("p") == {"a": 1}

    def test_extracts_json_from_surrounding_prose(self):
        nl = chr(10)
        reply = (
            "Here you go:" + nl + "```json" + nl + '{"a": 1}' + nl + "```" + nl + "Hope that helps."
        )
        assert StubAgent(reply).invoke_json("p") == {"a": 1}

    def test_no_json_raises_model_error(self):
        with pytest.raises(ModelError):
            StubAgent("no object here").invoke_json("p")

    def test_malformed_json_raises_model_error(self):
        with pytest.raises(ModelError):
            StubAgent('{"a": }').invoke_json("p")

    def test_model_error_is_a_medassist_error(self):
        assert issubclass(ModelError, CodeForgeError)


class TestBaseAgent:
    def test_agent_without_name_is_rejected(self):
        class Nameless(BaseAgent):
            pass

        with pytest.raises(ValueError):
            Nameless()
