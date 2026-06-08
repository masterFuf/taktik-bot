from taktik.core.social_media.instagram.workflows.scraping.scraping_workflow import ScrapingWorkflow


class _DummyDeviceManager:
    def __init__(self):
        self.device = object()


class _FakeAIService:
    vision_model = "vision-test"
    text_model = "text-test"


def test_scraping_workflow_builds_ai_service_from_injected_factory():
    captured = {}
    notifier = object()

    # Mirror the real factory signature (bridges/instagram/scraping/runtime/ai.py):
    # the workflow forwards api_key/ipc/vision_model/niche_taxonomy (premium taxonomy
    # injected by the front), not text_model.
    def factory(*, api_key, ipc=None, vision_model=None, text_model=None, niche_taxonomy=None):
        captured["api_key"] = api_key
        captured["ipc"] = ipc
        captured["vision_model"] = vision_model
        captured["niche_taxonomy"] = niche_taxonomy
        return _FakeAIService()

    workflow = ScrapingWorkflow(
        _DummyDeviceManager(),
        {
            "ai_mode": True,
            "openrouter_api_key": "test-key",
            "vision_model": "vision-model",
            "niche_taxonomy": {"fitness": ["gym", "yoga"]},
        },
        ai_notifier=notifier,
        ai_service_factory=factory,
    )

    assert workflow._ipc is notifier
    assert isinstance(workflow._ai_service, _FakeAIService)
    assert captured == {
        "api_key": "test-key",
        "ipc": notifier,
        "vision_model": "vision-model",
        "niche_taxonomy": {"fitness": ["gym", "yoga"]},
    }


def test_scraping_workflow_disables_ai_without_injected_factory():
    workflow = ScrapingWorkflow(
        _DummyDeviceManager(),
        {
            "ai_mode": True,
            "openrouter_api_key": "test-key",
        },
    )

    assert workflow._ai_service is None
