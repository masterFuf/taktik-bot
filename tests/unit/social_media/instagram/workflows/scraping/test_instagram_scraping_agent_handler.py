import pytest

from taktik.core.agent import AgentPlan, AgentPlanExecutor, PlanStep, WorkflowInvocation, WorkflowRegistry
from taktik.core.social_media.instagram.workflows.scraping import (
    INSTAGRAM_SCRAPING_HASHTAG_WORKFLOW_ID,
    INSTAGRAM_SCRAPING_POST_URL_WORKFLOW_ID,
    INSTAGRAM_SCRAPING_TARGET_WORKFLOW_ID,
    register_instagram_scraping_handlers,
)


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
