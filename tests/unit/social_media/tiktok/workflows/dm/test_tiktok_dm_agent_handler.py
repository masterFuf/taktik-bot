import pytest

from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows.dm import (
    TIKTOK_DM_READ_WORKFLOW_ID,
    TIKTOK_DM_SEND_WORKFLOW_ID,
    ConversationData,
    DMStats,
    register_tiktok_dm_handlers,
)


class FakeDMWorkflow:
    instances = []

    def __init__(self, device, config):
        self.device = device
        self.config = config
        self.stats = DMStats()
        self.callbacks = {}
        self.instances.append(self)

    def set_on_conversation_callback(self, callback):
        self.callbacks["conversation"] = callback

    def set_on_message_sent_callback(self, callback):
        self.callbacks["message_sent"] = callback

    def set_on_stats_callback(self, callback):
        self.callbacks["stats"] = callback

    def set_on_progress_callback(self, callback):
        self.callbacks["progress"] = callback

    def read_conversations(self):
        conversation = ConversationData(name="creator", messages=[{"text": "hello"}])
        self.stats.conversations_read = 1
        if "progress" in self.callbacks:
            self.callbacks["progress"](1, self.config.max_conversations, "creator")
        if "conversation" in self.callbacks:
            self.callbacks["conversation"](conversation.to_dict())
        if "stats" in self.callbacks:
            self.callbacks["stats"](self.stats.to_dict())
        return [conversation]

    def send_bulk_messages(self, messages):
        self.stats.messages_sent = 1
        result = {"conversation": messages[0]["conversation"], "success": True, "error": None}
        if "progress" in self.callbacks:
            self.callbacks["progress"](1, len(messages), messages[0]["conversation"])
        if "message_sent" in self.callbacks:
            self.callbacks["message_sent"](result)
        if "stats" in self.callbacks:
            self.callbacks["stats"](self.stats.to_dict())
        return [result]

    def get_stats(self):
        return self.stats


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def send(self, event_type, **payload):
        self.calls.append((event_type, payload))


def test_tiktok_dm_read_handler_executes_workflow_with_normalized_config():
    FakeDMWorkflow.instances = []
    registry = WorkflowRegistry()
    notifier = FakeNotifier()
    device = object()
    register_tiktok_dm_handlers(
        registry,
        device=device,
        notifier=notifier,
        workflow_factory=FakeDMWorkflow,
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
                        workflow_id=TIKTOK_DM_READ_WORKFLOW_ID,
                        params={
                            "maxConversations": 7,
                            "skipNotifications": "false",
                            "skipGroups": "true",
                            "onlyUnread": True,
                            "delayBetweenConversations": 1.5,
                            "markAsRead": "0",
                            "closeStickerSuggestions": "yes",
                        },
                    ),
                )
            ],
        )
    )

    workflow = FakeDMWorkflow.instances[0]
    assert workflow.device is device
    assert workflow.config.max_conversations == 7
    assert workflow.config.skip_notifications is False
    assert workflow.config.skip_groups is True
    assert workflow.config.only_unread is True
    assert workflow.config.delay_between_conversations == 1.5
    assert workflow.config.mark_as_read is False
    assert workflow.config.close_sticker_suggestions is True
    assert events[-1].payload["success"] is True
    assert events[-1].payload["conversations"][0]["name"] == "creator"
    assert ("dm_progress", {"current": 1, "total": 7, "name": "creator"}) in notifier.calls
    assert (
        "dm_conversation",
        {"conversation": {"name": "creator", "is_group": False, "member_count": None, "messages": [{"text": "hello"}], "last_message": None, "timestamp": None, "unread_count": 0, "can_reply": True}},
    ) in notifier.calls


def test_tiktok_dm_send_handler_executes_bulk_messages():
    FakeDMWorkflow.instances = []
    registry = WorkflowRegistry()
    notifier = FakeNotifier()
    register_tiktok_dm_handlers(
        registry,
        device=object(),
        notifier=notifier,
        workflow_factory=FakeDMWorkflow,
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
                        workflow_id=TIKTOK_DM_SEND_WORKFLOW_ID,
                        params={
                            "messages": [{"conversation": "creator", "message": "hello"}],
                            "delayBetweenMessages": 2.0,
                            "delayAfterSend": 0.75,
                        },
                    ),
                )
            ],
        )
    )

    workflow = FakeDMWorkflow.instances[0]
    assert workflow.config.delay_between_conversations == 2.0
    assert workflow.config.delay_after_send == 0.75
    assert events[-1].payload["success"] is True
    assert events[-1].payload["sent_count"] == 1
    assert events[-1].payload["results"] == [
        {"conversation": "creator", "success": True, "error": None}
    ]
    assert (
        "dm_sent",
        {"conversation": "creator", "success": True, "error": None},
    ) in notifier.calls


def test_tiktok_dm_send_handler_rejects_empty_messages_before_workflow_creation():
    FakeDMWorkflow.instances = []
    registry = WorkflowRegistry()
    register_tiktok_dm_handlers(
        registry,
        device=object(),
        workflow_factory=FakeDMWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    with pytest.raises(ValueError, match="requires at least one message"):
        executor.execute(
            AgentPlan(
                plan_id="plan-1",
                steps=[
                    PlanStep(
                        step_id="step-1",
                        workflow=WorkflowInvocation(
                            platform="tiktok",
                            workflow_id=TIKTOK_DM_SEND_WORKFLOW_ID,
                            params={"messages": []},
                        ),
                    )
                ],
            )
        )

    assert FakeDMWorkflow.instances == []
