from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows.for_you import (
    TIKTOK_FOR_YOU_WORKFLOW_ID,
    ForYouStats,
    register_tiktok_for_you_handlers,
)


class FakeForYouWorkflow:
    instances = []

    def __init__(self, device, config):
        self.device = device
        self.config = config
        self.callbacks = {}
        self.instances.append(self)

    def set_on_video_callback(self, callback):
        self.callbacks["video"] = callback

    def set_on_like_callback(self, callback):
        self.callbacks["like"] = callback

    def set_on_follow_callback(self, callback):
        self.callbacks["follow"] = callback

    def set_on_stats_callback(self, callback):
        self.callbacks["stats"] = callback

    def set_on_pause_callback(self, callback):
        self.callbacks["pause"] = callback

    def run(self):
        video = {"author": "creator", "description": "#one", "like_count": "42"}
        if "video" in self.callbacks:
            self.callbacks["video"](video)
        if "like" in self.callbacks:
            self.callbacks["like"](video)
        if "follow" in self.callbacks:
            self.callbacks["follow"](video)
        if "stats" in self.callbacks:
            self.callbacks["stats"]({"videos_watched": 1})
        if "pause" in self.callbacks:
            self.callbacks["pause"](8)
        return ForYouStats(videos_watched=1, videos_liked=1, users_followed=1)


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def send(self, event_type, **payload):
        self.calls.append((event_type, payload))


def test_register_tiktok_for_you_handler_executes_workflow_with_normalized_config():
    FakeForYouWorkflow.instances = []
    registry = WorkflowRegistry()
    notifier = FakeNotifier()
    device = object()

    register_tiktok_for_you_handlers(
        registry,
        device=device,
        notifier=notifier,
        workflow_factory=FakeForYouWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    events = executor.execute(
        AgentPlan(
            plan_id="plan-1",
            variables={"maxVideos": 20, "skipAds": True},
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="tiktok",
                        workflow_id=TIKTOK_FOR_YOU_WORKFLOW_ID,
                        params={
                            "maxVideos": 12,
                            "minWatchTime": 2.5,
                            "maxWatchTime": 7.5,
                            "likeProbability": 30,
                            "followProbability": 0.2,
                            "favoriteProbability": 5,
                            "requiredHashtags": ["#one", "two"],
                            "excludedHashtags": "spam, #ads",
                            "minLikes": "10",
                            "maxLikes": 500,
                            "maxLikesPerSession": 6,
                            "maxFollowsPerSession": 3,
                            "pauseAfterActions": 4,
                            "pauseDurationMin": 11,
                            "pauseDurationMax": 22,
                            "skipAlreadyLiked": "false",
                            "skipAlreadyFollowed": "0",
                            "skipAds": "yes",
                            "followBackSuggestions": "true",
                        },
                    ),
                )
            ],
        )
    )

    workflow = FakeForYouWorkflow.instances[0]
    assert workflow.device is device
    assert workflow.config.max_videos == 12
    assert workflow.config.min_watch_time == 2.5
    assert workflow.config.max_watch_time == 7.5
    assert workflow.config.like_probability == 0.3
    assert workflow.config.follow_probability == 0.2
    assert workflow.config.favorite_probability == 0.05
    assert workflow.config.required_hashtags == ["one", "two"]
    assert workflow.config.excluded_hashtags == ["spam", "ads"]
    assert workflow.config.min_likes == 10
    assert workflow.config.max_likes == 500
    assert workflow.config.max_likes_per_session == 6
    assert workflow.config.max_follows_per_session == 3
    assert workflow.config.pause_after_actions == 4
    assert workflow.config.pause_duration_min == 11
    assert workflow.config.pause_duration_max == 22
    assert workflow.config.skip_already_liked is False
    assert workflow.config.skip_already_followed is False
    assert workflow.config.skip_ads is True
    assert workflow.config.follow_back_suggestions is True
    assert events[-1].payload["success"] is True
    assert events[-1].payload["stats"]["videos_watched"] == 1
    assert ("video_info", {"video": {"author": "creator", "description": "#one", "like_count": "42"}}) in notifier.calls
    assert ("action", {"action": "like", "target": "creator"}) in notifier.calls
    assert ("action", {"action": "follow", "target": "creator"}) in notifier.calls
    assert ("tiktok_stats", {"stats": {"videos_watched": 1}}) in notifier.calls
    assert ("pause", {"duration": 8}) in notifier.calls
