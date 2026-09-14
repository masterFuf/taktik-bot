import pytest

from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry
from taktik.core.social_media.instagram.workflows.management import (
    INSTAGRAM_ACCOUNT_LIST_WORKFLOW_ID,
    INSTAGRAM_ACCOUNT_LOGIN_WORKFLOW_ID,
    INSTAGRAM_ACCOUNT_LOGOUT_WORKFLOW_ID,
    INSTAGRAM_ACCOUNT_REGISTER_WORKFLOW_ID,
    INSTAGRAM_ACCOUNT_SWITCH_WORKFLOW_ID,
    register_instagram_account_handlers,
)


class FakeWorkflow:
    instances = []

    def __init__(self, device, device_id):
        self.device = device
        self.device_id = device_id
        self.calls = []
        self.instances.append(self)

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return {"success": True, "message": "ok", "received": kwargs}


class FakeSwitchWorkflow(FakeWorkflow):
    def execute(self, target):
        self.calls.append(("switch_account", target))
        return {"success": True, "active_username": target}

    def list_accounts(self):
        self.calls.append(("list_accounts",))
        return {"success": True, "accounts": ["one", "two"]}


def test_instagram_account_login_handler_executes_with_bridge_compatible_params():
    FakeWorkflow.instances = []
    registry = WorkflowRegistry()
    device = object()

    register_instagram_account_handlers(
        registry,
        device=device,
        device_id="device-1",
        login_workflow_factory=FakeWorkflow,
    )

    events = AgentPlanExecutor(registry).execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="instagram",
                        workflow_id=INSTAGRAM_ACCOUNT_LOGIN_WORKFLOW_ID,
                        params={
                            "username": " target_user ",
                            "password": " secret ",
                            "maxRetries": "5",
                            "saveSession": False,
                            "saveLoginInfoInstagram": True,
                        },
                    ),
                )
            ],
        )
    )

    workflow = FakeWorkflow.instances[0]
    assert workflow.device is device
    assert workflow.device_id == "device-1"
    assert workflow.calls == [
        {
            "username": "target_user",
            "password": "secret",
            "max_retries": 5,
            "save_session": False,
            "use_saved_session": True,
            "save_login_info_instagram": True,
        }
    ]
    assert events[-1].payload["success"] is True


def test_instagram_account_logout_handler_executes_without_params():
    FakeWorkflow.instances = []
    registry = WorkflowRegistry()

    register_instagram_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        logout_workflow_factory=FakeWorkflow,
    )

    AgentPlanExecutor(registry).execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="instagram",
                        workflow_id=INSTAGRAM_ACCOUNT_LOGOUT_WORKFLOW_ID,
                        params={"ignored": "value"},
                    ),
                )
            ],
        )
    )

    assert FakeWorkflow.instances[0].calls == [{}]


def test_instagram_account_register_handler_validates_email_method():
    FakeWorkflow.instances = []
    registry = WorkflowRegistry()

    register_instagram_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        signup_workflow_factory=FakeWorkflow,
    )

    AgentPlanExecutor(registry).execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="instagram",
                        workflow_id=INSTAGRAM_ACCOUNT_REGISTER_WORKFLOW_ID,
                        params={"method": "email", "email": " user@example.com "},
                    ),
                )
            ],
        )
    )

    assert FakeWorkflow.instances[0].calls == [
        {"method": "email", "email": "user@example.com", "phone": None}
    ]


def test_instagram_account_login_rejects_missing_password_before_workflow_creation():
    FakeWorkflow.instances = []
    registry = WorkflowRegistry()

    register_instagram_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        login_workflow_factory=FakeWorkflow,
    )

    with pytest.raises(ValueError, match="Instagram login requires password"):
        AgentPlanExecutor(registry).execute(
            AgentPlan(
                plan_id="plan-1",
                steps=[
                    PlanStep(
                        step_id="step-1",
                        workflow=WorkflowInvocation(
                            platform="instagram",
                            workflow_id=INSTAGRAM_ACCOUNT_LOGIN_WORKFLOW_ID,
                            params={"username": "target_user"},
                        ),
                    )
                ],
            )
        )

    assert FakeWorkflow.instances == []


def test_instagram_account_register_rejects_missing_phone_before_workflow_creation():
    FakeWorkflow.instances = []
    registry = WorkflowRegistry()

    register_instagram_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        signup_workflow_factory=FakeWorkflow,
    )

    with pytest.raises(ValueError, match="Instagram register requires phone"):
        AgentPlanExecutor(registry).execute(
            AgentPlan(
                plan_id="plan-1",
                steps=[
                    PlanStep(
                        step_id="step-1",
                        workflow=WorkflowInvocation(
                            platform="instagram",
                            workflow_id=INSTAGRAM_ACCOUNT_REGISTER_WORKFLOW_ID,
                            params={"method": "phone"},
                        ),
                    )
                ],
            )
        )

    assert FakeWorkflow.instances == []


@pytest.mark.parametrize(
    ("workflow_id", "params", "expected_call"),
    [
        (
            INSTAGRAM_ACCOUNT_SWITCH_WORKFLOW_ID,
            {"targetUsername": "@creator"},
            ("switch_account", "@creator"),
        ),
        (INSTAGRAM_ACCOUNT_LIST_WORKFLOW_ID, {}, ("list_accounts",)),
    ],
)
def test_instagram_account_switch_handlers_use_existing_workflow_contract(
    workflow_id, params, expected_call
):
    FakeSwitchWorkflow.instances = []
    registry = WorkflowRegistry()
    register_instagram_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        switch_workflow_factory=FakeSwitchWorkflow,
    )

    events = AgentPlanExecutor(registry).execute(
        AgentPlan(
            plan_id="plan-switch",
            steps=[
                PlanStep(
                    step_id="step-switch",
                    workflow=WorkflowInvocation(
                        platform="instagram",
                        workflow_id=workflow_id,
                        params=params,
                    ),
                )
            ],
        )
    )

    assert FakeSwitchWorkflow.instances[0].calls == [expected_call]
    assert events[-1].payload["success"] is True


def test_instagram_account_switch_handler_requires_target_username():
    registry = WorkflowRegistry()
    register_instagram_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        switch_workflow_factory=FakeSwitchWorkflow,
    )

    with pytest.raises(ValueError, match="requires targetUsername"):
        registry.resolve(INSTAGRAM_ACCOUNT_SWITCH_WORKFLOW_ID)(
            WorkflowInvocation(
                platform="instagram",
                workflow_id=INSTAGRAM_ACCOUNT_SWITCH_WORKFLOW_ID,
            ),
            {},
        )


def test_instagram_account_switch_handler_uses_nonblank_compatible_alias():
    FakeSwitchWorkflow.instances = []
    registry = WorkflowRegistry()
    register_instagram_account_handlers(
        registry,
        device=object(),
        device_id="device-1",
        switch_workflow_factory=FakeSwitchWorkflow,
    )

    result = registry.resolve(INSTAGRAM_ACCOUNT_SWITCH_WORKFLOW_ID)(
        WorkflowInvocation(
            platform="instagram",
            workflow_id=INSTAGRAM_ACCOUNT_SWITCH_WORKFLOW_ID,
            params={"targetUsername": "creator"},
        ),
        {"target_username": "   "},
    )

    assert result["success"] is True
    assert FakeSwitchWorkflow.instances[0].calls == [("switch_account", "creator")]
