import pytest

from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry
from taktik.core.social_media.youtube.workflows.publish import (
    YOUTUBE_UPLOAD_POST_WORKFLOW_ID,
    register_youtube_publish_handlers,
)


class FakeYouTubeUploadWorkflow:
    instances = []

    def __init__(self, device, device_id):
        self.device = device
        self.device_id = device_id
        self.calls = []
        self.instances.append(self)

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return {"success": True, "message": "uploaded", "received": kwargs}


class FakeNotifier:
    def log(self, _level, _message):
        return None

    def status(self, _state, _message):
        return None


def test_register_youtube_publish_handler_executes_upload_workflow(tmp_path):
    FakeYouTubeUploadWorkflow.instances = []
    local_file = tmp_path / "video.mp4"
    local_file.write_bytes(b"video")
    registry = WorkflowRegistry()
    device = object()

    register_youtube_publish_handlers(
        registry,
        device=device,
        device_id="device-1",
        notifier=FakeNotifier(),
        workflow_factory=FakeYouTubeUploadWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    events = executor.execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="youtube",
                        workflow_id=YOUTUBE_UPLOAD_POST_WORKFLOW_ID,
                        params={
                            "localPath": str(local_file),
                            "title": "x" * 120,
                            "description": "description",
                            "uploadType": "short",
                            "visibility": "UNLISTED",
                        },
                    ),
                )
            ],
        )
    )

    workflow = FakeYouTubeUploadWorkflow.instances[0]
    assert workflow.device is device
    assert workflow.device_id == "device-1"
    assert workflow.calls == [
        {
            "local_path": str(local_file),
            "title": "x" * 100,
            "description": "description",
            "upload_type": "short",
            "visibility": "unlisted",
        }
    ]
    assert events[-1].payload["success"] is True


def test_youtube_publish_handler_rejects_missing_local_path_before_workflow_creation():
    FakeYouTubeUploadWorkflow.instances = []
    registry = WorkflowRegistry()
    register_youtube_publish_handlers(
        registry,
        device=object(),
        device_id="device-1",
        workflow_factory=FakeYouTubeUploadWorkflow,
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
                            platform="youtube",
                            workflow_id=YOUTUBE_UPLOAD_POST_WORKFLOW_ID,
                            params={"title": "missing path"},
                        ),
                    )
                ],
            )
        )

    assert FakeYouTubeUploadWorkflow.instances == []


def test_youtube_publish_handler_rejects_missing_file_before_workflow_creation(tmp_path):
    FakeYouTubeUploadWorkflow.instances = []
    registry = WorkflowRegistry()
    register_youtube_publish_handlers(
        registry,
        device=object(),
        device_id="device-1",
        workflow_factory=FakeYouTubeUploadWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    with pytest.raises(ValueError, match="File not found"):
        executor.execute(
            AgentPlan(
                plan_id="plan-1",
                steps=[
                    PlanStep(
                        step_id="step-1",
                        workflow=WorkflowInvocation(
                            platform="youtube",
                            workflow_id=YOUTUBE_UPLOAD_POST_WORKFLOW_ID,
                            params={"localPath": str(tmp_path / "missing.mp4")},
                        ),
                    )
                ],
            )
        )

    assert FakeYouTubeUploadWorkflow.instances == []
