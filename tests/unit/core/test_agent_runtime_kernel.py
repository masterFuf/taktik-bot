from taktik.core.agent import AgentAI, TaktikAgentWorkflow


class _DummyDeviceManager:
    def __init__(self):
        self.device = object()


class _FakeIPC:
    def __init__(self):
        self.calls = []

    def ai_screenshot_analyzing(self, **payload):
        self.calls.append(("ai_screenshot_analyzing", payload))

    def ai_screenshot_analyzed(self, **payload):
        self.calls.append(("ai_screenshot_analyzed", payload))

    def agent_decision(self, **payload):
        self.calls.append(("agent_decision", payload))


class _FakeAIService:
    vision_model = "vision-test"
    text_model = "text-test"

    def vision_completion(self, system_prompt, user_prompt, image_path, temperature=0.3, max_tokens=1500):
        return {
            "success": True,
            "text": '{"action": "like", "visit_profile": false, "comment": "", "reason": "relevant"}',
            "cost_usd": 0.42,
            "model": self.vision_model,
        }

    def text_completion(self, system_prompt, user_prompt, temperature=0.7, max_tokens=2000):
        return {"success": True, "content": '["growth"]'}


class _PublicPreviewAIService(_FakeAIService):
    def image_to_thumbnail_url(self, image_path, max_size=400):
        return "public-preview"


class _LegacyPreviewAIService(_FakeAIService):
    def _image_to_thumbnail_url(self, image_path, max_size=400):
        return "legacy-preview"


def test_taktik_agent_workflow_initializes_ai_from_injected_factory():
    captured = {}

    def factory(*, api_key, ipc=None, vision_model=None, text_model=None):
        captured["api_key"] = api_key
        captured["ipc"] = ipc
        captured["vision_model"] = vision_model
        captured["text_model"] = text_model
        return _FakeAIService()

    workflow = TaktikAgentWorkflow(
        device_manager=_DummyDeviceManager(),
        config={
            "openrouter_api_key": "test-key",
            "vision_model": "vision-model",
            "text_model": "text-model",
        },
        ai_service_factory=factory,
    )

    assert workflow._initialize_ai() is True
    assert captured == {
        "api_key": "test-key",
        "ipc": None,
        "vision_model": "vision-model",
        "text_model": "text-model",
    }
    assert isinstance(workflow._ai, AgentAI)


def test_taktik_agent_workflow_accepts_prebuilt_ai_service_without_api_key():
    workflow = TaktikAgentWorkflow(
        device_manager=_DummyDeviceManager(),
        config={},
        ai_service=_FakeAIService(),
    )

    assert workflow._initialize_ai() is True
    assert isinstance(workflow._ai, AgentAI)


def test_taktik_agent_workflow_requires_injected_ai_provider():
    workflow = TaktikAgentWorkflow(
        device_manager=_DummyDeviceManager(),
        config={"openrouter_api_key": "test-key"},
    )

    assert workflow._initialize_ai() is False


def test_agent_ai_prefers_public_thumbnail_builder_for_ipc_previews():
    ipc = _FakeIPC()
    agent_ai = AgentAI(ai_service=_PublicPreviewAIService(), ipc=ipc)

    decision = agent_ai.decide_feed_action(
        screenshot_path="unused.png",
        persona_block="persona",
        author_username="creator",
    )

    assert decision["action"] == "like"
    assert ipc.calls[0][0] == "ai_screenshot_analyzing"
    assert ipc.calls[0][1]["image_url"] == "public-preview"


def test_agent_ai_keeps_legacy_private_thumbnail_helper_as_fallback():
    ipc = _FakeIPC()
    agent_ai = AgentAI(ai_service=_LegacyPreviewAIService(), ipc=ipc)

    agent_ai.decide_feed_action(
        screenshot_path="unused.png",
        persona_block="persona",
        author_username="creator",
    )

    assert ipc.calls[0][1]["image_url"] == "legacy-preview"
