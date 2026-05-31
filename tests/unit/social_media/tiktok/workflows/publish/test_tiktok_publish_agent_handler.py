import pytest

from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry
from taktik.core.social_media.tiktok.workflows.publish import (
    TIKTOK_UPLOAD_POST_WORKFLOW_ID,
    register_tiktok_publish_handlers,
)


class FakeTikTokUploadWorkflow:
    instances = []

    def __init__(self, device, device_id, notifier=None):
        self.device = device
        self.device_id = device_id
        self.notifier = notifier
        self.calls = []
        self.instances.append(self)

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return {"success": True, "message": "published", "error_type": None, "received": kwargs}


def test_register_tiktok_publish_handler_executes_upload_workflow():
    FakeTikTokUploadWorkflow.instances = []
    registry = WorkflowRegistry()
    notifier = object()
    device = object()

    register_tiktok_publish_handlers(
        registry,
        device=device,
        device_id="device-1",
        notifier=notifier,
        workflow_factory=FakeTikTokUploadWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    events = executor.execute(
        AgentPlan(
            plan_id="plan-1",
            variables={"caption": "fallback"},
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="tiktok",
                        workflow_id=TIKTOK_UPLOAD_POST_WORKFLOW_ID,
                        params={
                            "localPath": "C:/media/video.mp4",
                            "caption": "caption",
                            "hashtags": ["one", 2],
                            "packageName": "com.bytedance.trill",
                        },
                    ),
                )
            ],
        )
    )

    workflow = FakeTikTokUploadWorkflow.instances[0]
    assert workflow.device is device
    assert workflow.device_id == "device-1"
    assert workflow.notifier is notifier
    assert workflow.calls == [
        {
            "local_path": "C:/media/video.mp4",
            "caption": "caption",
            "hashtags": ["one", "2"],
            "package_name": "com.bytedance.trill",
        }
    ]
    assert events[-1].payload["success"] is True
    assert events[-1].payload["received"]["local_path"] == "C:/media/video.mp4"


def test_tiktok_publish_handler_rejects_missing_local_path_before_workflow_creation():
    FakeTikTokUploadWorkflow.instances = []
    registry = WorkflowRegistry()
    register_tiktok_publish_handlers(
        registry,
        device=object(),
        device_id="device-1",
        workflow_factory=FakeTikTokUploadWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    with pytest.raises(ValueError, match="requires a non-empty localPath"):
        executor.execute(
            AgentPlan(
                plan_id="plan-1",
                steps=[
                    PlanStep(
                        step_id="step-1",
                        workflow=WorkflowInvocation(
                            platform="tiktok",
                            workflow_id=TIKTOK_UPLOAD_POST_WORKFLOW_ID,
                            params={"caption": "missing path"},
                        ),
                    )
                ],
            )
        )

    assert FakeTikTokUploadWorkflow.instances == []
