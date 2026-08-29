import pytest

from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows.dm import (
    TIKTOK_DM_ACTIVITY_WORKFLOW_ID,
    TIKTOK_DM_REQUESTS_WORKFLOW_ID,
    TIKTOK_DM_UNREPLIED_WORKFLOW_ID,
    TIKTOK_NEW_FOLLOWERS_WORKFLOW_ID,
    register_tiktok_inbox_handlers,
)


class FakeDMWorkflow:
    instances = []

    def __init__(self, device, config):
        self.device = device
        self.config = config
        self.callbacks = {}
        self.calls = []
        self.instances.append(self)

    def _emit(self, name, item):
        callback = self.callbacks.get(name)
        if callback is not None:
            callback(item)

    def set_on_new_follower_callback(self, callback):
        self.callbacks["new_follower"] = callback

    def set_on_follow_back_result_callback(self, callback):
        self.callbacks["follow_back_result"] = callback

    def set_on_unreplied_callback(self, callback):
        self.callbacks["unreplied"] = callback

    def set_on_message_request_callback(self, callback):
        self.callbacks["message_request"] = callback

    def set_on_request_result_callback(self, callback):
        self.callbacks["request_result"] = callback

    def set_on_notification_callback(self, callback):
        self.callbacks["notification"] = callback

    def read_new_followers(self, max_items=50):
        self.calls.append(("read_new_followers", max_items))
        follower = {"username": "creator", "followed_back": False}
        self._emit("new_follower", follower)
        return [follower]

    def follow_back_users(self, usernames):
        self.calls.append(("follow_back_users", usernames))
        results = [{"username": name, "success": True} for name in usernames]
        for result in results:
            self._emit("follow_back_result", result)
        return results

    def read_unreplied_conversations(self, max_items=30, only_unreplied=True):
        self.calls.append(("read_unreplied_conversations", max_items, only_unreplied))
        conversations = [
            {"username": "creator", "unreplied": True},
            {"username": "other", "unreplied": False},
        ]
        for conversation in conversations:
            self._emit("unreplied", conversation)
        return conversations

    def read_message_requests(self, max_items=30):
        self.calls.append(("read_message_requests", max_items))
        request = {"username": "stranger", "preview": "salut"}
        self._emit("message_request", request)
        return [request]

    def process_message_requests(self, decisions):
        self.calls.append(("process_message_requests", decisions))
        results = [{"username": d["username"], "success": True} for d in decisions]
        for result in results:
            self._emit("request_result", result)
        return results

    def read_notifications(self, max_items=20):
        self.calls.append(("read_notifications", max_items))
        notification = {"category": "activity", "title": "a aime votre video"}
        self._emit("notification", notification)
        return [notification]


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def send(self, event_type, **payload):
        self.calls.append((event_type, payload))


def _run(workflow_id, params, notifier=None):
    FakeDMWorkflow.instances = []
    registry = WorkflowRegistry()
    device = object()
    register_tiktok_inbox_handlers(
        registry,
        device=device,
        notifier=notifier,
        workflow_factory=FakeDMWorkflow,
    )
    events = AgentPlanExecutor(registry).execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="tiktok", workflow_id=workflow_id, params=params
                    ),
                )
            ],
        )
    )
    return events, device


def test_new_followers_scrape_returns_the_list_the_bridge_only_emits():
    notifier = FakeNotifier()
    events, device = _run(TIKTOK_NEW_FOLLOWERS_WORKFLOW_ID, {"maxItems": 12}, notifier)

    workflow = FakeDMWorkflow.instances[0]
    assert workflow.device is device
    assert workflow.calls == [("read_new_followers", 12)]
    assert events[-1].payload["mode"] == "scrape"
    assert events[-1].payload["count"] == 1
    assert events[-1].payload["followers"][0]["username"] == "creator"
    assert ("new_follower", {"follower": {"username": "creator", "followed_back": False}}) in notifier.calls


def test_new_followers_follow_back_mode_uses_the_selected_usernames():
    events, _ = _run(
        TIKTOK_NEW_FOLLOWERS_WORKFLOW_ID,
        {"mode": "follow_back", "usernames": ["creator", "@other"], "delayBetweenActions": 2.5},
    )

    workflow = FakeDMWorkflow.instances[0]
    assert workflow.config.delay_between_conversations == 2.5
    assert workflow.calls == [("follow_back_users", ["creator", "other"])]
    assert events[-1].payload["followed_count"] == 2


def test_follow_back_without_usernames_never_reaches_the_device():
    with pytest.raises(ValueError):
        _run(TIKTOK_NEW_FOLLOWERS_WORKFLOW_ID, {"mode": "follow_back", "usernames": []})
    assert FakeDMWorkflow.instances[0].calls == []


def test_unreplied_counts_only_the_unanswered_conversations():
    notifier = FakeNotifier()
    events, _ = _run(
        TIKTOK_DM_UNREPLIED_WORKFLOW_ID, {"maxItems": 5, "onlyUnreplied": "false"}, notifier
    )

    assert FakeDMWorkflow.instances[0].calls == [("read_unreplied_conversations", 5, False)]
    assert events[-1].payload["count"] == 2
    assert events[-1].payload["unreplied_count"] == 1
    assert ("unreplied_conversation", {"conversation": {"username": "creator", "unreplied": True}}) in notifier.calls


def test_message_requests_scrape_defaults_to_thirty_items():
    events, _ = _run(TIKTOK_DM_REQUESTS_WORKFLOW_ID, {})

    assert FakeDMWorkflow.instances[0].calls == [("read_message_requests", 30)]
    assert events[-1].payload["requests"][0]["username"] == "stranger"


def test_message_requests_execute_keeps_only_well_formed_decisions():
    events, _ = _run(
        TIKTOK_DM_REQUESTS_WORKFLOW_ID,
        {
            "mode": "execute",
            "decisions": [
                {"username": "@stranger", "action": "Accept", "message": "salut"},
                {"username": "ghost", "action": "maybe"},
                {"username": "", "action": "decline"},
                "not-a-mapping",
            ],
        },
    )

    assert FakeDMWorkflow.instances[0].calls == [
        ("process_message_requests", [{"username": "stranger", "action": "accept", "message": "salut"}])
    ]
    assert events[-1].payload["processed_count"] == 1


def test_message_requests_execute_without_a_usable_decision_is_refused():
    with pytest.raises(ValueError):
        _run(TIKTOK_DM_REQUESTS_WORKFLOW_ID, {"mode": "execute", "decisions": [{"action": "accept"}]})
    assert FakeDMWorkflow.instances[0].calls == []


def test_activity_read_is_read_only_and_returns_its_notifications():
    notifier = FakeNotifier()
    events, _ = _run(TIKTOK_DM_ACTIVITY_WORKFLOW_ID, {"maxItems": 9}, notifier)

    assert FakeDMWorkflow.instances[0].calls == [("read_notifications", 9)]
    assert events[-1].payload["notifications"][0]["category"] == "activity"
    assert notifier.calls[0][0] == "activity_notification"


def test_the_four_ids_are_reachable_from_the_standalone_cli_registry():
    from taktik.cli.common.registry_builder import build_registry

    build = build_registry(device=object(), device_id="agent")
    for workflow_id in (
        TIKTOK_NEW_FOLLOWERS_WORKFLOW_ID,
        TIKTOK_DM_UNREPLIED_WORKFLOW_ID,
        TIKTOK_DM_REQUESTS_WORKFLOW_ID,
        TIKTOK_DM_ACTIVITY_WORKFLOW_ID,
    ):
        assert workflow_id in build.workflow_ids
