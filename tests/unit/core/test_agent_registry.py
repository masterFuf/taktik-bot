from taktik.core.agent import (
    AgentPlan,
    AgentPlanExecutor,
    MissingWorkflowHandlersError,
    PlanStep,
    WorkflowInvocation,
    WorkflowRegistry,
)


def test_workflow_registry_registers_and_resolves_handlers():
    registry = WorkflowRegistry()

    def handler(invocation, payload):
        return {"workflow": invocation.workflow_id, "payload": payload}

    registry.register("instagram.feed.browse", handler)

    assert registry.contains("instagram.feed.browse") is True
    assert tuple(registry.workflow_ids()) == ("instagram.feed.browse",)
    assert registry.resolve("instagram.feed.browse") is handler


def test_workflow_registry_rejects_duplicate_workflow_ids():
    registry = WorkflowRegistry()
    registry.register("instagram.feed.browse", lambda invocation, payload: {})

    try:
        registry.register("instagram.feed.browse", lambda invocation, payload: {})
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("Expected duplicate workflow registration to fail")


def test_workflow_registry_reports_missing_plan_handlers_once():
    registry = WorkflowRegistry()
    registry.register("instagram.automation.feed", lambda invocation, payload: {})

    plan = AgentPlan(
        plan_id="plan-1",
        steps=[
            PlanStep(
                step_id="step-1",
                workflow=WorkflowInvocation(
                    platform="instagram",
                    workflow_id="instagram.automation.feed",
                ),
            ),
            PlanStep(
                step_id="step-2",
                workflow=WorkflowInvocation(
                    platform="tiktok",
                    workflow_id="tiktok.automation.for_you",
                ),
            ),
            PlanStep(
                step_id="step-3",
                workflow=WorkflowInvocation(
                    platform="tiktok",
                    workflow_id="tiktok.automation.for_you",
                ),
            ),
        ],
    )

    assert registry.missing_for_plan(plan) == ("tiktok.automation.for_you",)


def test_agent_plan_executor_runs_registered_steps_and_emits_events():
    registry = WorkflowRegistry()
    events = []

    def handler(invocation, payload):
        return {"workflow": invocation.workflow_id, "account": payload["account_username"]}

    registry.register("instagram.feed.browse", handler)
    executor = AgentPlanExecutor(registry, event_sink=events.append)

    plan = AgentPlan(
        plan_id="plan-1",
        source="desktop",
        platform="instagram",
        variables={"account_username": "bot_account"},
        steps=[
            PlanStep(
                step_id="step-1",
                workflow=WorkflowInvocation(
                    platform="instagram",
                    workflow_id="instagram.feed.browse",
                    params={"session_mode": "feed"},
                ),
            )
        ],
    )

    emitted = executor.execute(plan)

    assert [event.status for event in emitted] == ["started", "completed"]
    assert [event.status for event in events] == ["started", "completed"]
    assert emitted[-1].payload == {
        "workflow": "instagram.feed.browse",
        "account": "bot_account",
    }


def test_agent_plan_executor_rejects_missing_handlers_before_partial_execution():
    registry = WorkflowRegistry()
    events = []
    calls = []

    def handler(invocation, payload):
        calls.append(invocation.workflow_id)
        return {}

    registry.register("instagram.automation.feed", handler)
    executor = AgentPlanExecutor(registry, event_sink=events.append)

    plan = AgentPlan(
        plan_id="plan-1",
        steps=[
            PlanStep(
                step_id="step-1",
                workflow=WorkflowInvocation(
                    platform="instagram",
                    workflow_id="instagram.automation.feed",
                ),
            ),
            PlanStep(
                step_id="step-2",
                workflow=WorkflowInvocation(
                    platform="tiktok",
                    workflow_id="tiktok.automation.for_you",
                ),
            ),
        ],
    )

    try:
        executor.execute(plan)
    except MissingWorkflowHandlersError as exc:
        assert exc.workflow_ids == ("tiktok.automation.for_you",)
        assert exc.to_payload() == {
            "error_type": "missing_workflow_handlers",
            "message": "No workflow handler registered for: tiktok.automation.for_you",
            "workflow_ids": ["tiktok.automation.for_you"],
        }
    else:
        raise AssertionError("Expected missing workflow handler preflight to fail")

    assert events == []
    assert calls == []
