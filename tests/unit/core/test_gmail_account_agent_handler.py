import pytest

from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry
from taktik.core.app.email.gmail.workflows import (
    GMAIL_ACCOUNT_LOGIN_WORKFLOW_ID,
    GMAIL_ACCOUNT_READ_OTP_WORKFLOW_ID,
    GMAIL_ACCOUNT_SCAN_ACCOUNTS_WORKFLOW_ID,
    register_gmail_account_handlers,
)


class FakeGmailWorkflow:
    instances = []

    def __init__(self, device, device_id, notifier=None):
        self.device = device
        self.device_id = device_id
        self.notifier = notifier
        self.ensure_kwargs = None
        self.read_kwargs = None
        self.instances.append(self)

    def ensure_account_added(self, **kwargs):
        self.ensure_kwargs = kwargs
        return {"success": True, "message": "added", "error_type": None}

    def get_latest_verification_code(self, **kwargs):
        self.read_kwargs = kwargs
        return {"success": True, "code": "123456", "message": "found", "error_type": None}

    def scan_accounts(self):
        return {
            "success": True,
            "accounts": [{"email": "creator@example.com"}, {"email": "other@example.com"}],
            "message": "2 account(s) found",
            "error_type": None,
        }


class FakeNotifier:
    pass


def test_gmail_login_handler_executes_workflow_and_persists_on_success():
    FakeGmailWorkflow.instances = []
    persisted = []
    registry = WorkflowRegistry()
    device = object()
    notifier = FakeNotifier()
    register_gmail_account_handlers(
        registry,
        device=device,
        device_id="device-1",
        notifier=notifier,
        account_persister=persisted.append,
        workflow_factory=FakeGmailWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    events = executor.execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="gmail",
                        workflow_id=GMAIL_ACCOUNT_LOGIN_WORKFLOW_ID,
                        params={"email": "creator@example.com", "password": "secret"},
                    ),
                )
            ],
        )
    )

    workflow = FakeGmailWorkflow.instances[0]
    assert workflow.device is device
    assert workflow.device_id == "device-1"
    assert workflow.notifier is notifier
    assert workflow.ensure_kwargs == {"email": "creator@example.com", "password": "secret"}
    assert persisted == ["creator@example.com"]
    assert events[-1].payload["success"] is True


def test_gmail_read_otp_handler_executes_with_filters():
    FakeGmailWorkflow.instances = []
    registry = WorkflowRegistry()
    register_gmail_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        workflow_factory=FakeGmailWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    executor.execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="gmail",
                        workflow_id=GMAIL_ACCOUNT_READ_OTP_WORKFLOW_ID,
                        params={
                            "email": "creator@example.com",
                            "senderFilter": "TikTok",
                            "subjectFilter": "code",
                            "timeout": "30",
                        },
                    ),
                )
            ],
        )
    )

    assert FakeGmailWorkflow.instances[0].read_kwargs == {
        "email": "creator@example.com",
        "sender_filter": "TikTok",
        "subject_filter": "code",
        "timeout": 30,
    }


def test_gmail_scan_accounts_persists_discovered_accounts():
    FakeGmailWorkflow.instances = []
    persisted = []
    registry = WorkflowRegistry()
    register_gmail_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        account_persister=persisted.append,
        workflow_factory=FakeGmailWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    executor.execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="gmail",
                        workflow_id=GMAIL_ACCOUNT_SCAN_ACCOUNTS_WORKFLOW_ID,
                    ),
                )
            ],
        )
    )

    assert persisted == ["creator@example.com", "other@example.com"]


def test_gmail_login_rejects_missing_email_before_workflow_creation():
    FakeGmailWorkflow.instances = []
    registry = WorkflowRegistry()
    register_gmail_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        workflow_factory=FakeGmailWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    with pytest.raises(ValueError, match="requires email"):
        executor.execute(
            AgentPlan(
                plan_id="plan-1",
                steps=[
                    PlanStep(
                        step_id="step-1",
                        workflow=WorkflowInvocation(
                            platform="gmail",
                            workflow_id=GMAIL_ACCOUNT_LOGIN_WORKFLOW_ID,
                            params={"password": "secret"},
                        ),
                    )
                ],
            )
        )

    assert FakeGmailWorkflow.instances == []
