import pytest

from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry
from taktik.core.social_media.tiktok.workflows.management import (
    TIKTOK_ACCOUNT_LOGIN_WORKFLOW_ID,
    TIKTOK_ACCOUNT_LOGOUT_WORKFLOW_ID,
    TIKTOK_ACCOUNT_REGISTER_WORKFLOW_ID,
    register_tiktok_account_handlers,
)


class FakeWorkflow:
    instances = []

    def __init__(self, device, device_id, notifier=None):
        self.device = device
        self.device_id = device_id
        self.notifier = notifier
        self.execute_kwargs = None
        self.instances.append(self)

    def execute(self, **kwargs):
        self.execute_kwargs = kwargs
        return {"success": True, "message": "ok", "error_type": None}


class FakeNotifier:
    pass


def test_tiktok_account_login_handler_executes_with_normalized_params():
    FakeWorkflow.instances = []
    registry = WorkflowRegistry()
    device = object()
    notifier = FakeNotifier()
    register_tiktok_account_handlers(
        registry,
        device=device,
        device_id="device-1",
        notifier=notifier,
        login_workflow_factory=FakeWorkflow,
        logout_workflow_factory=FakeWorkflow,
        signup_workflow_factory=FakeWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    events = executor.execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="tiktok",
                        workflow_id=TIKTOK_ACCOUNT_LOGIN_WORKFLOW_ID,
                        params={
                            "username": "creator",
                            "password": "secret",
                            "maxRetries": "4",
                            "saveSession": "false",
                        },
                    ),
                )
            ],
        )
    )

    workflow = FakeWorkflow.instances[0]
    assert workflow.device is device
    assert workflow.device_id == "device-1"
    assert workflow.notifier is notifier
    assert workflow.execute_kwargs == {
        "username": "creator",
        "password": "secret",
        "max_retries": 4,
        "save_session": False,
    }
    assert events[-1].payload["success"] is True


def test_tiktok_account_logout_handler_executes_without_params():
    FakeWorkflow.instances = []
    registry = WorkflowRegistry()
    register_tiktok_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        login_workflow_factory=FakeWorkflow,
        logout_workflow_factory=FakeWorkflow,
        signup_workflow_factory=FakeWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    executor.execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="tiktok",
                        workflow_id=TIKTOK_ACCOUNT_LOGOUT_WORKFLOW_ID,
                    ),
                )
            ],
        )
    )

    assert FakeWorkflow.instances[0].execute_kwargs == {}


def test_tiktok_account_register_handler_executes_with_email_params():
    FakeWorkflow.instances = []
    registry = WorkflowRegistry()
    register_tiktok_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        login_workflow_factory=FakeWorkflow,
        logout_workflow_factory=FakeWorkflow,
        signup_workflow_factory=FakeWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    executor.execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="tiktok",
                        workflow_id=TIKTOK_ACCOUNT_REGISTER_WORKFLOW_ID,
                        params={
                            "method": "email",
                            "email": "creator@example.com",
                            "phoneCountry": "France",
                            "birthYear": 1994,
                            "birthMonth": 7,
                            "birthDay": 8,
                            "gmailPassword": "gmail-secret",
                            "tiktokPassword": "TikTok#123",
                            "nickname": "creator",
                        },
                    ),
                )
            ],
        )
    )

    assert FakeWorkflow.instances[0].execute_kwargs == {
        "method": "email",
        "email": "creator@example.com",
        "phone": None,
        "phone_country": "France",
        "birth_year": 1994,
        "birth_month": 7,
        "birth_day": 8,
        "gmail_password": "gmail-secret",
        "tiktok_password": "TikTok#123",
        "nickname": "creator",
    }


def test_tiktok_account_login_rejects_missing_password_before_workflow_creation():
    FakeWorkflow.instances = []
    registry = WorkflowRegistry()
    register_tiktok_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        login_workflow_factory=FakeWorkflow,
        logout_workflow_factory=FakeWorkflow,
        signup_workflow_factory=FakeWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    with pytest.raises(ValueError, match="requires password"):
        executor.execute(
            AgentPlan(
                plan_id="plan-1",
                steps=[
                    PlanStep(
                        step_id="step-1",
                        workflow=WorkflowInvocation(
                            platform="tiktok",
                            workflow_id=TIKTOK_ACCOUNT_LOGIN_WORKFLOW_ID,
                            params={"username": "creator"},
                        ),
                    )
                ],
            )
        )

    assert FakeWorkflow.instances == []
