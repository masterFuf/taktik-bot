import pytest

import taktik.core.database.tiktok_scraping as scraping_store
from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows.scraping import (
    TIKTOK_AUTOMATION_SCRAPING_WORKFLOW_ID,
    TIKTOK_STANDALONE_SCRAPING_WORKFLOW_ID,
    register_tiktok_scraping_handlers,
)
from taktik.core.social_media.tiktok.actions.business.workflows.scraping.models import ScrapingStats


class FakeNavigation:
    def __init__(self, device):
        self.device = device


class FakeScrapingWorkflow:
    instances = []

    def __init__(self, device, navigation, config):
        self.device = device
        self.navigation = navigation
        self.config = config
        self.stats = ScrapingStats()
        self.completion_reason = None
        self.callbacks = {}
        self.instances.append(self)

    def set_on_status_callback(self, callback):
        self.callbacks["status"] = callback

    def set_on_progress_callback(self, callback):
        self.callbacks["progress"] = callback

    def set_on_profile_callback(self, callback):
        self.callbacks["profile"] = callback

    def set_on_save_profile_callback(self, callback):
        self.callbacks["save_profile"] = callback

    def set_on_error_callback(self, callback):
        self.callbacks["error"] = callback

    def run(self):
        profile = {"username": "creator", "followers_count": 42}
        self.stats.profiles_scraped = 1
        if "status" in self.callbacks:
            self.callbacks["status"]("scraping", "Scraping profiles")
        if "progress" in self.callbacks:
            self.callbacks["progress"](1, self.config.max_profiles, "creator")
        if "profile" in self.callbacks:
            self.callbacks["profile"](profile)
        if "save_profile" in self.callbacks:
            self.callbacks["save_profile"](profile)
        self.completion_reason = "completed"
        return [profile]


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def send(self, event_type, **payload):
        self.calls.append((event_type, payload))


@pytest.fixture(autouse=True)
def store(monkeypatch):
    """The scraping session rows, recorded instead of written."""
    rows = []
    monkeypatch.setattr(scraping_store, "open_scraping_session",
                        lambda source_type, source_name: rows.append(("open", source_type, source_name)) or 7)
    monkeypatch.setattr(scraping_store, "save_scraped_profile",
                        lambda session_id, profile: rows.append(("profile", session_id, dict(profile))))
    monkeypatch.setattr(scraping_store, "close_scraping_session",
                        lambda *args: rows.append(("close", *args)))
    return rows


def test_register_tiktok_scraping_handler_executes_target_workflow(store):
    FakeScrapingWorkflow.instances = []
    registry = WorkflowRegistry()
    notifier = FakeNotifier()
    device = object()

    register_tiktok_scraping_handlers(
        registry,
        device=device,
        notifier=notifier,
        navigation_factory=FakeNavigation,
        workflow_factory=FakeScrapingWorkflow,
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
                        workflow_id=TIKTOK_STANDALONE_SCRAPING_WORKFLOW_ID,
                        params={
                            "type": "target",
                            "targetUsernames": ["@creator"],
                            "scrapeType": "following",
                            "maxProfiles": 12,
                            "maxPosts": 7,
                            "enrichProfiles": "false",
                            "maxProfilesToEnrich": 3,
                        },
                    ),
                )
            ],
        )
    )

    workflow = FakeScrapingWorkflow.instances[0]
    assert workflow.device is device
    assert workflow.navigation.device is device
    assert workflow.config.scrape_type == "target"
    assert workflow.config.target_usernames == ["@creator"]
    assert workflow.config.target_scrape_type == "following"
    assert workflow.config.max_profiles == 12
    assert workflow.config.max_videos == 7
    assert workflow.config.enrich_profiles is False
    assert workflow.config.max_profiles_to_enrich == 3
    assert events[-1].payload["success"] is True
    assert events[-1].payload["total_scraped"] == 1
    assert events[-1].payload["profiles"][0]["username"] == "creator"
    # The session and its profile are filed from the handler too, as the desktop bridge files them.
    assert store == [
        ("open", "FOLLOWING", "@creator"),
        ("profile", 7, {"username": "creator", "followers_count": 42}),
        ("close", 7, 1, "COMPLETED", 0),
    ]
    assert ("status", {"status": "scraping", "message": "Scraping profiles"}) in notifier.calls
    assert (
        "scraping_progress",
        {"scraped": 1, "total": 12, "current": "creator"},
    ) in notifier.calls
    # The desktop's `scraping_profile` event, from the handler as from the bridge.
    profile_events = [payload for kind, payload in notifier.calls if kind == "scraping_profile"]
    assert len(profile_events) == 1
    assert {key: value for key, value in profile_events[0].items() if key != "scrapedAt"} == {
        "username": "creator", "followersCount": 42, "followingCount": 0,
    }
    assert ("scraping_completed", {"totalScraped": 1}) in notifier.calls
    assert notifier.calls[-1] == ("status", {"status": "completed", "message": "Scraped 1 profiles"})
    # The row's id reaches the desktop before any live event: a killed bridge never closes it.
    assert notifier.calls[0] == ("scraping_session", {"scraping_id": 7, "platform": "tiktok"})
    assert [kind for kind, _ in notifier.calls].count("scraping_session") == 1


def test_a_run_told_not_to_save_files_nothing(store):
    FakeScrapingWorkflow.instances = []
    registry = WorkflowRegistry()
    register_tiktok_scraping_handlers(
        registry,
        device=object(),
        navigation_factory=FakeNavigation,
        workflow_factory=FakeScrapingWorkflow,
    )

    result = registry.resolve(TIKTOK_AUTOMATION_SCRAPING_WORKFLOW_ID)(
        WorkflowInvocation(platform="tiktok", workflow_id=TIKTOK_AUTOMATION_SCRAPING_WORKFLOW_ID,
                           params={"type": "hashtag", "hashtag": "food", "saveToDb": False}),
        {},
    )

    assert result["total_scraped"] == 1
    assert result["session_id"] is None
    assert store == []


def test_a_row_that_could_not_be_written_is_not_announced(store, monkeypatch):
    monkeypatch.setattr(scraping_store, "open_scraping_session", lambda source_type, source_name: None)
    notifier = FakeNotifier()
    registry = WorkflowRegistry()
    register_tiktok_scraping_handlers(
        registry,
        device=object(),
        notifier=notifier,
        navigation_factory=FakeNavigation,
        workflow_factory=FakeScrapingWorkflow,
    )

    registry.resolve(TIKTOK_AUTOMATION_SCRAPING_WORKFLOW_ID)(
        WorkflowInvocation(platform="tiktok", workflow_id=TIKTOK_AUTOMATION_SCRAPING_WORKFLOW_ID,
                           params={"type": "hashtag", "hashtag": "food"}),
        {},
    )

    assert "scraping_session" not in [kind for kind, _ in notifier.calls]


def test_tiktok_scraping_handler_accepts_hashtag_workflow_id():
    FakeScrapingWorkflow.instances = []
    registry = WorkflowRegistry()
    register_tiktok_scraping_handlers(
        registry,
        device=object(),
        navigation_factory=FakeNavigation,
        workflow_factory=FakeScrapingWorkflow,
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
                        workflow_id=TIKTOK_AUTOMATION_SCRAPING_WORKFLOW_ID,
                        params={"type": "hashtag", "hashtag": "#food"},
                    ),
                )
            ],
        )
    )

    assert FakeScrapingWorkflow.instances[0].config.scrape_type == "hashtag"
    assert FakeScrapingWorkflow.instances[0].config.hashtag == "food"


def test_tiktok_scraping_handler_rejects_missing_target_before_workflow_creation():
    FakeScrapingWorkflow.instances = []
    registry = WorkflowRegistry()
    register_tiktok_scraping_handlers(
        registry,
        device=object(),
        navigation_factory=FakeNavigation,
        workflow_factory=FakeScrapingWorkflow,
    )
    executor = AgentPlanExecutor(registry)

    with pytest.raises(ValueError, match="requires targetUsernames"):
        executor.execute(
            AgentPlan(
                plan_id="plan-1",
                steps=[
                    PlanStep(
                        step_id="step-1",
                        workflow=WorkflowInvocation(
                            platform="tiktok",
                            workflow_id=TIKTOK_STANDALONE_SCRAPING_WORKFLOW_ID,
                            params={"type": "target"},
                        ),
                    )
                ],
            )
        )

    assert FakeScrapingWorkflow.instances == []
