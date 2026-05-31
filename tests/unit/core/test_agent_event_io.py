import json

from taktik.core.agent import AgentEvent, agent_event_to_payload, agent_events_to_payload


def test_agent_event_to_payload_returns_json_safe_dict():
    payload = agent_event_to_payload(
        AgentEvent(
            event_type="plan_step",
            status="completed",
            step_id="step-1",
            workflow_id="instagram.automation.feed",
            message="Done",
            payload={"likes": 2},
        )
    )

    assert payload == {
        "event_type": "plan_step",
        "status": "completed",
        "step_id": "step-1",
        "workflow_id": "instagram.automation.feed",
        "message": "Done",
        "payload": {"likes": 2},
    }
    json.dumps(payload)


def test_agent_events_to_payload_serializes_iterable():
    payload = agent_events_to_payload(
        [
            AgentEvent(event_type="plan_step", status="started", step_id="step-1"),
            AgentEvent(event_type="plan_step", status="completed", step_id="step-1"),
        ]
    )

    assert [event["status"] for event in payload] == ["started", "completed"]
