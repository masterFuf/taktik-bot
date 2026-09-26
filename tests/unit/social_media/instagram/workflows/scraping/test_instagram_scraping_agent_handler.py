from pathlib import Path

import pytest
import yaml

from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry
from taktik.core.compat.selectors.setup import INSTAGRAM_TARGET_VERSION, apply_version_overrides
from taktik.core.social_media.instagram.ui.selectors import PROFILE_SELECTORS
from taktik.core.social_media.instagram.workflows.core import runtime_setup
from taktik.core.social_media.instagram.workflows.scraping import (
    INSTAGRAM_SCRAPING_HASHTAG_WORKFLOW_ID,
    INSTAGRAM_SCRAPING_POST_URL_WORKFLOW_ID,
    INSTAGRAM_SCRAPING_TARGET_WORKFLOW_ID,
    register_instagram_scraping_handlers,
    run_instagram_scraping,
)

OVERRIDES = Path(runtime_setup.__file__).resolve().parents[4] / "compat" / "data" / "overrides" / "instagram.yaml"


@pytest.fixture(autouse=True)
def detections(monkeypatch):
    """The language detection, recorded: a real one reads a screen and filters the catalogs."""
    seen = []
    monkeypatch.setattr(runtime_setup, "detect_and_optimize", lambda device: seen.append(device) or "en")
    return seen


class FakeScrapingWorkflow:
    instances = []

    def __init__(self, device_manager, config, ai_notifier=None, ai_service_factory=None):
        self.device_manager = device_manager
        self.config = config
        self.ai_notifier = ai_notifier
        self.ai_service_factory = ai_service_factory
        self.instances.append(self)

    def run(self):
        return {"success": True, "total_scraped": 3, "config": self.config}


def test_instagram_target_scraping_handler_builds_bridge_compatible_config():
    FakeScrapingWorkflow.instances = []
    registry = WorkflowRegistry()
    device_manager = object()
    ai_notifier = object()
    ai_service_factory = object()

    register_instagram_scraping_handlers(
        registry,
        device_manager=device_manager,
        ai_notifier=ai_notifier,
        instagram_scraping_ai_service=ai_service_factory,
        workflow_factory=FakeScrapingWorkflow,
    )

    events = AgentPlanExecutor(registry).execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="instagram",
                        workflow_id=INSTAGRAM_SCRAPING_TARGET_WORKFLOW_ID,
                        params={
                            "targetUsernames": [" user_a ", "user_b"],
                            "scrapeType": "following",
                            "maxProfiles": "25",
                            "saveToDb": False,
                            "deepQualify": True,
                            "deepQualifyMaxFollowing": "12",
                            "ai": {
                                "enabled": True,
                                "profileAnalysis": False,
                                "niche": "fitness",
                                "qualificationPrompt": "qualify",
                                "openrouterApiKey": "key",
                                "visionModel": "model",
                            },
                        },
                    ),
                )
            ],
        )
    )

    workflow = FakeScrapingWorkflow.instances[0]
    assert workflow.device_manager is device_manager
    assert workflow.ai_notifier is ai_notifier
    assert workflow.ai_service_factory is ai_service_factory
    assert workflow.config == {
        "type": "target",
        "session_duration_minutes": 60,
        "max_profiles": 25,
        "export_csv": True,
        "save_to_db": False,
        "enrich_profiles": False,
        # The reading the bridge had and the handler lacked: filters, location, taxonomy.
        "fetchLocation": False,
        "requireProfilePicture": False,
        "skipPrivateProfiles": True,
        "response_language": "en",
        "deep_qualify": True,
        "deep_qualify_max_following": 12,
        "target_usernames": ["user_a", "user_b"],
        "scrape_type": "following",
        "scrape_post_likers": True,
        "scrape_post_commenters": False,
        "ai_mode": True,
        "ai_profile_analysis": False,
        "ai_niche": "fitness",
        "ai_qualification_prompt": "qualify",
        "openrouter_api_key": "key",
        "vision_model": "model",
        "niche_taxonomy": {},
        "ai_rescrape_mode": "full",
    }
    assert events[-1].payload["success"] is True


def test_instagram_hashtag_scraping_handler_accepts_legacy_single_hashtag():
    FakeScrapingWorkflow.instances = []
    registry = WorkflowRegistry()
    register_instagram_scraping_handlers(
        registry,
        device_manager=object(),
        workflow_factory=FakeScrapingWorkflow,
    )

    AgentPlanExecutor(registry).execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="instagram",
                        workflow_id=INSTAGRAM_SCRAPING_HASHTAG_WORKFLOW_ID,
                        params={"hashtag": " dev ", "maxPosts": "7"},
                    ),
                )
            ],
        )
    )

    assert FakeScrapingWorkflow.instances[0].config["hashtags"] == ["dev"]
    assert FakeScrapingWorkflow.instances[0].config["hashtag"] == "dev"
    assert FakeScrapingWorkflow.instances[0].config["max_posts"] == 7


def test_instagram_post_url_scraping_handler_extracts_post_id():
    FakeScrapingWorkflow.instances = []
    registry = WorkflowRegistry()
    register_instagram_scraping_handlers(
        registry,
        device_manager=object(),
        workflow_factory=FakeScrapingWorkflow,
    )

    AgentPlanExecutor(registry).execute(
        AgentPlan(
            plan_id="plan-1",
            steps=[
                PlanStep(
                    step_id="step-1",
                    workflow=WorkflowInvocation(
                        platform="instagram",
                        workflow_id=INSTAGRAM_SCRAPING_POST_URL_WORKFLOW_ID,
                        params={"postUrl": "https://www.instagram.com/reel/ABC123/"},
                    ),
                )
            ],
        )
    )

    assert FakeScrapingWorkflow.instances[0].config["post_urls"] == [
        "https://www.instagram.com/reel/ABC123/"
    ]
    assert FakeScrapingWorkflow.instances[0].config["post_id"] == "ABC123"


def test_instagram_target_scraping_requires_target_usernames_before_workflow_creation():
    FakeScrapingWorkflow.instances = []
    registry = WorkflowRegistry()
    register_instagram_scraping_handlers(
        registry,
        device_manager=object(),
        workflow_factory=FakeScrapingWorkflow,
    )

    with pytest.raises(ValueError, match="requires targetUsernames"):
        AgentPlanExecutor(registry).execute(
            AgentPlan(
                plan_id="plan-1",
                steps=[
                    PlanStep(
                        step_id="step-1",
                        workflow=WorkflowInvocation(
                            platform="instagram",
                            workflow_id=INSTAGRAM_SCRAPING_TARGET_WORKFLOW_ID,
                            params={"maxProfiles": 10},
                        ),
                    )
                ],
            )
        )

    assert FakeScrapingWorkflow.instances == []


@pytest.mark.parametrize("workflow_id, params, expected", [
    ("instagram.scraping.usernames", {"usernames": ["first", "second"], "sourceName": "list"},
     {"usernames": ["first", "second"], "source_name": "list"}),
    ("instagram.scraping.profile_posts", {"targetUsernames": ["brand"], "maxPostsPerTarget": 4},
     {"target_usernames": ["brand"], "scrape_type": "profile_posts", "max_posts_per_target": 4}),
])
def test_the_usernames_and_profile_posts_sources_have_their_ids(workflow_id, params, expected):
    FakeScrapingWorkflow.instances = []
    registry = WorkflowRegistry()
    register_instagram_scraping_handlers(registry, device_manager=object(), workflow_factory=FakeScrapingWorkflow)

    registry.resolve(workflow_id)(
        WorkflowInvocation(platform="instagram", workflow_id=workflow_id, params=params), {}
    )

    config = FakeScrapingWorkflow.instances[0].config
    assert {key: config[key] for key in expected} == expected


@pytest.mark.parametrize("workflow_id, message", [
    ("instagram.scraping.usernames", "requires usernames"),
    ("instagram.scraping.profile_posts", "requires targetUsernames"),
    ("instagram.scraping.hashtag", "requires hashtags"),
    ("instagram.scraping.post_url", "requires postUrls"),
])
def test_a_source_without_anything_to_scrape_is_refused_before_the_start(workflow_id, message):
    FakeScrapingWorkflow.instances = []
    starts = []
    registry = WorkflowRegistry()
    register_instagram_scraping_handlers(
        registry,
        device_manager=object(),
        instagram_start=lambda package_name: starts.append(package_name) or True,
        workflow_factory=FakeScrapingWorkflow,
    )

    with pytest.raises(ValueError, match=message):
        registry.resolve(workflow_id)(
            WorkflowInvocation(platform="instagram", workflow_id=workflow_id, params={}), {}
        )
    assert starts == [] and FakeScrapingWorkflow.instances == []


class _Phone:
    """A connected device manager; the device is never touched here."""

    def __init__(self):
        self.device = object()


@pytest.fixture
def back_to_baseline():
    yield
    apply_version_overrides("instagram", INSTAGRAM_TARGET_VERSION)


def test_the_launcher_matches_the_selectors_to_the_phone_before_the_workflow(detections, back_to_baseline):
    """Instagram 447, app in English: the 447 overrides are in the catalogs and the language has been
    read when the workflow is built, so its first localized read already faces the phone's app."""
    phone = _Phone()
    seen_when_built = {}

    class Workflow(FakeScrapingWorkflow):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            seen_when_built["bio"] = list(PROFILE_SELECTORS.bio)
            seen_when_built["detections"] = list(detections)

    run_instagram_scraping(
        {"type": "target", "targetUsernames": ["alpha"]},
        device_manager=phone,
        instagram_installed_version=lambda: "447.0.0.55.81",
        workflow_factory=Workflow,
    )

    entries = yaml.safe_load(OVERRIDES.read_text(encoding="utf-8"))["versions"]["447.0.0.0"]
    assert seen_when_built["bio"] == entries["profile.bio"]
    assert seen_when_built["detections"] == [phone.device]


def test_without_a_version_reader_the_language_is_still_read(detections, monkeypatch):
    """The connection has already applied the official app's overrides; the language is the launcher's."""
    applied = []
    monkeypatch.setattr("taktik.core.compat.selectors.setup.apply_version_overrides",
                        lambda platform, version: applied.append(version) or 0)
    phone = _Phone()

    run_instagram_scraping({"type": "usernames", "usernames": ["alpha"]}, device_manager=phone,
                           workflow_factory=FakeScrapingWorkflow)

    assert applied == []
    assert detections == [phone.device]


def test_the_cli_handler_passes_its_version_reader(detections, monkeypatch):
    applied = []
    monkeypatch.setattr("taktik.core.compat.selectors.setup.apply_version_overrides",
                        lambda platform, version: applied.append((platform, version)) or 0)
    registry = WorkflowRegistry()
    register_instagram_scraping_handlers(registry, device_manager=_Phone(), workflow_factory=FakeScrapingWorkflow,
                                         instagram_installed_version=lambda: "447.0.0.55.81")

    registry.resolve(INSTAGRAM_SCRAPING_HASHTAG_WORKFLOW_ID)(
        WorkflowInvocation(platform="instagram", workflow_id=INSTAGRAM_SCRAPING_HASHTAG_WORKFLOW_ID,
                           params={"hashtag": "dev"}), {}
    )

    assert applied == [("instagram", "447.0.0.55.81")]
    assert len(detections) == 1
