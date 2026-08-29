"""Lambda handler for the Orchestrator.

Routes a free-text engineering request to a specialist and runs it.
"""

from __future__ import annotations

from src.agents.codeforge import AGENTS, OrchestratorAgent
from src.lambdas._base import run_stage

DISPATCH = {
    "planner": lambda d: (d.get("issue") or d["request"], d.get("files")),
    "coder": lambda d: (d.get("task") or d["request"], d.get("files"), d.get("plan")),
    "reviewer": lambda d: (d.get("diff") or d["request"], d.get("context", "")),
}


def _route_and_run(data: dict) -> dict:
    decision = OrchestratorAgent().run(data["request"])
    name = decision["agent"]

    # The sandbox is not a model agent, so the orchestrator cannot run it the
    # same way. Routing there is reported rather than executed: running code
    # is an explicit action, not something a router should trigger.
    if name == "sandbox":
        return {
            "routed_to": "sandbox",
            "routing_reason": decision.get("reason"),
            "output": {
                "note": "Send the code to POST /v1/run to execute it. "
                        "Execution is not triggered implicitly by routing.",
            },
        }

    return {
        "routed_to": name,
        "routing_reason": decision.get("reason"),
        "output": AGENTS[name]().run(*DISPATCH[name](data)),
    }


def handler(event: dict, context: object) -> dict:
    return run_stage(event, required=["request"], fn=_route_and_run)
