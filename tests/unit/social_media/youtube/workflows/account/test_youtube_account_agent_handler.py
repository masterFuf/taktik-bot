import pytest

from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry
from taktik.core.social_media.youtube.workflows.account import (
    YOUTUBE_ACCOUNT_LOGIN_WORKFLOW_ID,
    YOUTUBE_ACCOUNT_LOGOUT_WORKFLOW_ID,
    register_youtube_account_handlers,
)


class FakeYouTubeAccountWorkflow:
    instances = []

    def __init__(self, device, device_id, notifier=None, account_repository=None):
        self.device = device
        self.device_id = device_id
        self.notifier = notifier
        self.account_repository = account_repository
        self.calls = []
        self.instances.append(self)

    def login(self, **kwargs):
        self.calls.append(("login", kwargs))
        return {"success": True, "message": "logged in", "received": kwargs}

    def logout(self, **kwargs):
        self.calls.append(("logout", kwargs))
        return {"success": True, "message": "logged out", "received": kwargs}


def test_youtube_account_login_handler_executes_workflow():
    FakeYouTubeAccountWorkflow.instances = []
    registry = WorkflowRegistry()
    device = object()
    notifier = object()
    repository = object()

    register_youtube_account_handlers(
        registry,
        device=device,
        device_id="device-1",
        notifier=notifier,
        account_repository=repository,
        workflow_factory=FakeYouTubeAccountWorkflow,
    )

    events = AgentPlanExecutor(registry).execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="youtube",
                        workflow_id=YOUTUBE_ACCOUNT_LOGIN_WORKFLOW_ID,
                        params={"email": " user@example.com ", "password": " secret "},
                    ),
                )
            ],
        )
    )

    workflow = FakeYouTubeAccountWorkflow.instances[0]
    assert workflow.device is device
    assert workflow.device_id == "device-1"
    assert workflow.notifier is notifier
    assert workflow.account_repository is repository
    assert workflow.calls == [
        ("login", {"email": "user@example.com", "password": "secret"})
    ]
    assert events[-1].payload["success"] is True


def test_youtube_account_logout_handler_executes_workflow_without_email():
    FakeYouTubeAccountWorkflow.instances = []
    registry = WorkflowRegistry()
    register_youtube_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        workflow_factory=FakeYouTubeAccountWorkflow,
    )

    AgentPlanExecutor(registry).execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="youtube",
                        workflow_id=YOUTUBE_ACCOUNT_LOGOUT_WORKFLOW_ID,
                        params={},
                    ),
                )
            ],
        )
    )

    assert FakeYouTubeAccountWorkflow.instances[0].calls == [
        ("logout", {"email": ""})
    ]


def test_youtube_account_login_rejects_missing_email_before_workflow_creation():
    FakeYouTubeAccountWorkflow.instances = []
    registry = WorkflowRegistry()
    register_youtube_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        workflow_factory=FakeYouTubeAccountWorkflow,
    )

    with pytest.raises(ValueError, match="YouTube login requires email"):
        AgentPlanExecutor(registry).execute(
            AgentPlan(
                plan_id="plan-1",
                steps=[
                    PlanStep(
                        step_id="step-1",
                        workflow=WorkflowInvocation(
                            platform="youtube",
                            workflow_id=YOUTUBE_ACCOUNT_LOGIN_WORKFLOW_ID,
                            params={"password": "secret"},
                        ),
                    )
                ],
            )
        )

    assert FakeYouTubeAccountWorkflow.instances == []
