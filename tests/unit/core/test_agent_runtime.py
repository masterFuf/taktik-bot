import pytest

from taktik.core.agent import AgentRuntime, WorkflowRegistry


def test_agent_runtime_executes_payload_through_injected_registry():
    registry = WorkflowRegistry()
    events = []

    def handler(invocation, payload):
        return {
            "workflow": invocation.workflow_id,
            "account": payload["account_username"],
            "limit": payload["limit"],
        }

    registry.register("instagram.automation.feed", handler)
    runtime = AgentRuntime(registry=registry, event_sink=events.append)

    emitted = runtime.execute_payload(
        {
            "plan_id": "plan-1",
            "source": "desktop",
            "variables": {"account_username": "bot"},
            "steps": [
                {
                    "step_id": "step-1",
                    "workflow": {
                        "platform": "instagram",
                        "workflow_id": "instagram.automation.feed",
                        "params": {"limit": 5},
                    },
                }
            ],
        }
    )

    assert [event.status for event in emitted] == ["started", "completed"]
    assert [event.status for event in events] == ["started", "completed"]
    assert emitted[-1].payload == {
        "workflow": "instagram.automation.feed",
        "account": "bot",
        "limit": 5,
    }


def test_agent_runtime_rejects_unknown_manifest_workflow_before_registry_resolution():
    registry = WorkflowRegistry()
    runtime = AgentRuntime(registry=registry)

    with pytest.raises(ValueError, match="Unknown workflow_id"):
        runtime.execute_payload(
            {
                "plan_id": "plan-1",
                "steps": [
                    {
                        "step_id": "step-1",
                        "workflow": {
                            "platform": "instagram",
                            "workflow_id": "instagram.automation.missing",
                        },
                    }
                ],
            }
        )
