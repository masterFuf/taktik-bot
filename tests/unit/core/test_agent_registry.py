from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry


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
