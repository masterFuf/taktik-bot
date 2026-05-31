from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow import (
    TIKTOK_UNFOLLOW_WORKFLOW_ID,
    UnfollowStats,
    register_tiktok_unfollow_handlers,
)


class FakeUnfollowWorkflow:
    instances = []

    def __init__(self, device, config):
        self.device = device
        self.config = config
        self.callbacks = {}
        self.instances.append(self)

    def set_on_unfollow_callback(self, callback):
        self.callbacks["unfollow"] = callback

    def set_on_skip_callback(self, callback):
        self.callbacks["skip"] = callback

    def set_on_stats_callback(self, callback):
        self.callbacks["stats"] = callback

    def run(self):
        if "unfollow" in self.callbacks:
            self.callbacks["unfollow"]("creator", 1)
        if "skip" in self.callbacks:
            self.callbacks["skip"]("friend")
        if "stats" in self.callbacks:
            self.callbacks["stats"]({"unfollowed": 1, "skipped_friends": 1, "errors": 0})
        return UnfollowStats(unfollowed=1, skipped_friends=1)


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def send(self, event_type, **payload):
        self.calls.append((event_type, payload))


def test_register_tiktok_unfollow_handler_executes_workflow_with_normalized_config():
    FakeUnfollowWorkflow.instances = []
    registry = WorkflowRegistry()
    notifier = FakeNotifier()
    device = object()

    register_tiktok_unfollow_handlers(
        registry,
        device=device,
        notifier=notifier,
        workflow_factory=FakeUnfollowWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    events = executor.execute(
        AgentPlan(
            plan_id="plan-1",
            variables={"maxUnfollows": 20},
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="tiktok",
                        workflow_id=TIKTOK_UNFOLLOW_WORKFLOW_ID,
                        params={
                            "maxUnfollows": 7,
                            "skipFriends": False,
                            "minDelay": 0.5,
                            "maxDelay": 1.5,
                            "maxScrollAttempts": 4,
                        },
                    ),
                )
            ],
        )
    )

    workflow = FakeUnfollowWorkflow.instances[0]
    assert workflow.device is device
    assert workflow.config.max_unfollows == 7
    assert workflow.config.include_friends is True
    assert workflow.config.min_delay == 0.5
    assert workflow.config.max_delay == 1.5
    assert workflow.config.max_scroll_attempts == 4
    assert events[-1].payload["success"] is True
    assert events[-1].payload["stats"]["unfollowed"] == 1
    assert (
        "unfollow_event",
        {"event": "unfollowed", "username": "creator", "count": 1},
    ) in notifier.calls
    assert (
        "unfollow_event",
        {"event": "skipped", "reason": "friends", "username": "friend"},
    ) in notifier.calls
    assert (
        "unfollow_stats",
        {"stats": {"unfollowed": 1, "skipped_friends": 1, "errors": 0, "target": 7}},
    ) in notifier.calls


def test_tiktok_unfollow_handler_keeps_skip_friends_default():
    FakeUnfollowWorkflow.instances = []
    registry = WorkflowRegistry()
    register_tiktok_unfollow_handlers(
        registry,
        device=object(),
        workflow_factory=FakeUnfollowWorkflow,
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
                        workflow_id=TIKTOK_UNFOLLOW_WORKFLOW_ID,
                        params={},
                    ),
                )
            ],
        )
    )

    assert FakeUnfollowWorkflow.instances[0].config.include_friends is False
