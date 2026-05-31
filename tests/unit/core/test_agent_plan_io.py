import pytest

from taktik.core.agent import agent_plan_from_payload, agent_plan_to_payload, load_workflow_manifest


def test_agent_plan_from_payload_builds_plan_with_workflow_step():
    plan = agent_plan_from_payload(
        {
            "plan_id": "plan-1",
            "source": "desktop",
            "platform": "instagram",
            "variables": {"account_username": "bot"},
            "steps": [
                {
                    "step_id": "step-1",
                    "workflow": {
                        "platform": "instagram",
                        "workflow_id": "instagram.automation.feed",
                        "params": {"max_posts": 10},
                    },
                }
            ],
        },
        manifest=load_workflow_manifest(),
    )

    assert plan.plan_id == "plan-1"
    assert plan.steps[0].workflow.workflow_id == "instagram.automation.feed"
    assert plan.steps[0].workflow.params == {"max_posts": 10}


def test_agent_plan_to_payload_roundtrips_json_safe_dict():
    plan = agent_plan_from_payload(
        {
            "plan_id": "plan-1",
            "steps": [
                {
                    "step_id": "step-1",
                    "workflow": {
                        "platform": "tiktok",
                        "workflow_id": "tiktok.standalone.upload_post",
                    },
                }
            ],
        }
    )

    assert agent_plan_to_payload(plan) == {
        "plan_id": "plan-1",
        "source": "standalone",
        "platform": "multi",
        "steps": [
            {
                "step_id": "step-1",
                "kind": "workflow",
                "workflow": {
                    "platform": "tiktok",
                    "workflow_id": "tiktok.standalone.upload_post",
                    "params": {},
                },
                "conditions": [],
                "metadata": {},
            }
        ],
        "variables": {},
        "metadata": {},
    }


def test_agent_plan_from_payload_rejects_unknown_manifest_workflow_id():
    with pytest.raises(ValueError, match="Unknown workflow_id"):
        agent_plan_from_payload(
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
            },
            manifest=load_workflow_manifest(),
        )
