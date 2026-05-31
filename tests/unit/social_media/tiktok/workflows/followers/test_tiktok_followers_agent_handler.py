import pytest

from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows.followers import (
    TIKTOK_FOLLOWERS_WORKFLOW_ID,
    FollowersStats,
    register_tiktok_followers_handlers,
)


class FakeFollowersWorkflow:
    instances = []

    def __init__(self, device, config):
        self.device = device
        self.config = config
        self.callbacks = {}
        self.instances.append(self)

    def set_on_stats_callback(self, callback):
        self.callbacks["stats"] = callback

    def set_on_action_callback(self, callback):
        self.callbacks["action"] = callback

    def set_on_pause_callback(self, callback):
        self.callbacks["pause"] = callback

    def run(self, bot_username=None):
        self.bot_username = bot_username
        if "stats" in self.callbacks:
            self.callbacks["stats"]({"profiles_visited": 1})
        if "action" in self.callbacks:
            self.callbacks["action"]({"action": "profile_visit", "target": "creator"})
        if "pause" in self.callbacks:
            self.callbacks["pause"](12)
        return FollowersStats(profiles_visited=1, likes=2, follows=3, completion_reason="completed")


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def send(self, event_type, **payload):
        self.calls.append((event_type, payload))


def test_register_tiktok_followers_handler_executes_single_target_workflow():
    FakeFollowersWorkflow.instances = []
    registry = WorkflowRegistry()
    notifier = FakeNotifier()
    device = object()

    register_tiktok_followers_handlers(
        registry,
        device=device,
        notifier=notifier,
        workflow_factory=FakeFollowersWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    events = executor.execute(
        AgentPlan(
            plan_id="plan-1",
            variables={"botUsername": "bot_account"},
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="tiktok",
                        workflow_id=TIKTOK_FOLLOWERS_WORKFLOW_ID,
                        params={
                            "searchQuery": "@target",
                            "maxFollowers": 12,
                            "postsPerProfile": 3,
                            "minWatchTime": 4.5,
                            "maxWatchTime": 9.5,
                            "likeProbability": 75,
                            "commentProbability": 10,
                            "shareProbability": 5,
                            "favoriteProbability": 0.25,
                            "followProbability": 40,
                            "storyLikeProbability": 20,
                            "maxLikesPerSession": 7,
                            "maxFollowsPerSession": 2,
                            "maxCommentsPerSession": 1,
                            "minDelay": 0.5,
                            "maxDelay": 1.5,
                            "pauseAfterActions": 4,
                            "pauseDurationMin": 10,
                            "pauseDurationMax": 20,
                            "includeFriends": "true",
                            "skipPrivateAccounts": "yes",
                            "maxConsecutiveKnownUsernames": 9,
                        },
                    ),
                )
            ],
        )
    )

    workflow = FakeFollowersWorkflow.instances[0]
    assert workflow.device is device
    assert workflow.bot_username == "bot_account"
    assert workflow.config.search_query == "target"
    assert workflow.config.max_followers == 12
    assert workflow.config.posts_per_profile == 3
    assert workflow.config.min_watch_time == 4.5
    assert workflow.config.max_watch_time == 9.5
    assert workflow.config.like_probability == 0.75
    assert workflow.config.comment_probability == 0.1
    assert workflow.config.share_probability == 0.05
    assert workflow.config.favorite_probability == 0.25
    assert workflow.config.follow_probability == 0.4
    assert workflow.config.story_like_probability == 0.2
    assert workflow.config.max_likes_per_session == 7
    assert workflow.config.max_follows_per_session == 2
    assert workflow.config.max_comments_per_session == 1
    assert workflow.config.min_delay == 0.5
    assert workflow.config.max_delay == 1.5
    assert workflow.config.pause_after_actions == 4
    assert workflow.config.pause_duration_min == 10
    assert workflow.config.pause_duration_max == 20
    assert workflow.config.include_friends is True
    assert workflow.config.skip_private_accounts is True
    assert workflow.config.max_consecutive_known_usernames == 9
    assert events[-1].payload["success"] is True
    assert events[-1].payload["stats"]["profiles_visited"] == 1
    assert ("followers_stats", {"stats": {"profiles_visited": 1}}) in notifier.calls
    assert ("action", {"action": "profile_visit", "target": "creator"}) in notifier.calls
    assert ("pause", {"duration": 12}) in notifier.calls


def test_tiktok_followers_handler_rejects_missing_target_before_workflow_creation():
    FakeFollowersWorkflow.instances = []
    registry = WorkflowRegistry()
    register_tiktok_followers_handlers(
        registry,
        device=object(),
        workflow_factory=FakeFollowersWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    with pytest.raises(ValueError, match="requires a non-empty searchQuery"):
        executor.execute(
            AgentPlan(
                plan_id="plan-1",
                steps=[
                    PlanStep(
                        step_id="step-1",
                        workflow=WorkflowInvocation(
                            platform="tiktok",
                            workflow_id=TIKTOK_FOLLOWERS_WORKFLOW_ID,
                            params={"maxFollowers": 5},
                        ),
                    )
                ],
            )
        )

    assert FakeFollowersWorkflow.instances == []
