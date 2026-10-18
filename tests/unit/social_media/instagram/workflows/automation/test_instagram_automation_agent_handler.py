import pytest

from taktik.core.kernel.contracts import WorkflowInvocation
from taktik.core.kernel.registry import WorkflowRegistry
from taktik.core.social_media.instagram.workflows.common.startup import (
    InstagramRunPhone,
    InstagramStartError,
    package_name_from_payload,
)
from taktik.core.social_media.instagram.workflows.automation.agent_handler import (
    INSTAGRAM_AUTOMATION_WORKFLOW_IDS,
    build_instagram_automation_handler,
    instagram_automation_payload,
    register_instagram_automation_handlers,
)


class FakeAutomation:
    def __init__(self, device_manager):
        self.device_manager = device_manager
        self.device = device_manager.device
        self.stats = {"likes": 2}
        self.ran = False

    def run_workflow(self):
        self.ran = True

    def final_stats(self):
        return {"likes": 3}


class FakeDeviceManager:
    device = object()


def _connect(connected=None, start=None, installed_version=None):
    """The host's `connect`: the package it was asked for goes to `connected`."""

    def connect(package_name):
        if connected is not None:
            connected.append(package_name)
        return InstagramRunPhone(device_manager=FakeDeviceManager(), start=start,
                                 installed_version=installed_version)

    return connect


def test_instagram_automation_handler_runs_workflow_with_bridge_config():
    runtime_calls = []
    ai_calls = []
    logs = []
    automations = []
    connected = []
    starts = []

    def workflow_factory(device_manager):
        automation = FakeAutomation(device_manager)
        automations.append(automation)
        return automation

    def runtime_setup(**kwargs):
        runtime_calls.append(kwargs)
        kwargs["automation"].config = kwargs["workflow_config"]

    def ai_service_factory(ai_config):
        return {"api": ai_config["openrouterApiKey"]}

    handler = build_instagram_automation_handler(
        instagram_connect=_connect(connected, start=lambda: starts.append("start") or True,
                                   installed_version=lambda: "321"),
        instagram_ai_service=ai_service_factory,
        workflow_factory=workflow_factory,
        runtime_setup=runtime_setup,
        ai_hook_installer=lambda **kwargs: ai_calls.append(kwargs),
        log=lambda level, message: logs.append((level, message)),
    )

    result = handler(
        WorkflowInvocation(
            platform="instagram",
            workflow_id="instagram.automation.target_followers",
            params={
                "targetUsername": "alpha",
                "limits": {"maxProfiles": 5},
                "ai": {"enabled": True, "openrouterApiKey": "key"},
                "packageName": "com.instagram.android.c1",
            },
        ),
        {},
    )

    # The run's totals come from the ledger (`final_stats`), as the desktop's final event does.
    assert result == {"success": True, "stats": {"likes": 3}}
    assert automations[0].ran is True
    assert connected == ["com.instagram.android.c1"]
    assert starts == ["start"]
    assert runtime_calls[0]["workflow_config"]["actions"][0]["target_username"] == "alpha"
    assert runtime_calls[0]["package_name"] == "com.instagram.android.c1"
    assert runtime_calls[0]["installed_version_provider"]() == "321"
    assert ai_calls[0]["ai"] == {"api": "key"}
    assert ai_calls[0]["device"] is FakeDeviceManager.device
    assert logs == []


def test_the_handler_hands_the_whole_payload_to_the_config_builder():
    runtime_calls = []
    handler = build_instagram_automation_handler(
        instagram_connect=_connect(),
        workflow_factory=FakeAutomation,
        runtime_setup=lambda **kwargs: runtime_calls.append(kwargs),
    )

    handler(
        WorkflowInvocation(
            platform="instagram",
            workflow_id="instagram.automation.target_followers",
            params={
                "target": "alpha,beta",
                "distribution": "interleaved",
                "warmupPolicy": {"maxActionsPerSession": 7},
                "behaviorPolicy": {"profile": "prudent"},
            },
        ),
        {},
    )

    config = runtime_calls[0]["workflow_config"]
    assert config["session_settings"]["warmup_policy"]["max_actions_per_session"] == 7
    assert config["behaviorPolicy"] == {"profile": "prudent"}
    assert config["actions"][0]["distribution"] == "interleaved"


def test_the_payload_keeps_every_key_and_adds_the_terminal_aliases():
    payload = instagram_automation_payload(
        WorkflowInvocation(
            platform="instagram",
            workflow_id="instagram.automation.feed",
            params={"feed_stories": {"enabled": True}, "appLanguage": "fr", "package_name": "com.taktik.ig1",
                    "feed": {"captureAds": True}, "workflowType": "hashtags"},
        ),
        {"deviceId": "emulator-5554"},
    )

    assert payload["workflowType"] == "feed", "the id names the workflow"
    assert payload["target"] == "feed"
    assert payload["feedStories"] == {"enabled": True}
    assert payload["language"] == "fr"
    # The clone's terminal name stays as typed: the launcher reads it, as every Instagram launcher.
    assert package_name_from_payload(payload) == "com.taktik.ig1"
    assert payload["feed"] == {"captureAds": True}
    assert payload["deviceId"] == "emulator-5554"


def test_a_start_that_fails_runs_nothing():
    automations = []
    handler = build_instagram_automation_handler(
        instagram_connect=_connect(start=lambda: False),
        workflow_factory=lambda dm: automations.append(dm),
        runtime_setup=lambda **kwargs: None,
    )

    with pytest.raises(InstagramStartError):
        handler(
            WorkflowInvocation(platform="instagram", workflow_id="instagram.automation.feed", params={}),
            {},
        )
    assert automations == []


def test_instagram_automation_handler_defaults_feed_target():
    runtime_calls = []

    handler = build_instagram_automation_handler(
        instagram_connect=_connect(),
        workflow_factory=FakeAutomation,
        runtime_setup=lambda **kwargs: runtime_calls.append(kwargs),
    )

    handler(
        WorkflowInvocation(
            platform="instagram",
            workflow_id="instagram.automation.feed",
            params={},
        ),
        {},
    )

    assert runtime_calls[0]["workflow_config"]["actions"][0]["type"] == "feed"


def test_instagram_automation_handler_requires_target_for_target_workflows():
    connected = []
    handler = build_instagram_automation_handler(
        instagram_connect=_connect(connected),
        workflow_factory=FakeAutomation,
        runtime_setup=lambda **kwargs: None,
    )

    with pytest.raises(ValueError, match="requires target"):
        handler(
            WorkflowInvocation(
                platform="instagram",
                workflow_id="instagram.automation.target_followers",
                params={},
            ),
            {},
        )
    assert connected == []


def test_a_payload_the_reader_refuses_never_asks_the_host_for_the_phone():
    connected = []
    automations = []
    handler = build_instagram_automation_handler(
        instagram_connect=_connect(connected),
        workflow_factory=lambda dm: automations.append(dm),
        runtime_setup=lambda **kwargs: None,
    )

    with pytest.raises(ValueError, match="limits.maxProfiles = 501"):
        handler(
            WorkflowInvocation(platform="instagram", workflow_id="instagram.automation.feed",
                               params={"limits": {"maxProfiles": 501}}),
            {},
        )
    assert connected == [] and automations == []


def test_a_handler_without_a_host_that_connects_says_so():
    handler = build_instagram_automation_handler(workflow_factory=FakeAutomation)

    with pytest.raises(RuntimeError, match="connects the phone"):
        handler(WorkflowInvocation(platform="instagram", workflow_id="instagram.automation.feed", params={}), {})


def test_register_instagram_automation_handlers_registers_manifest_ids():
    registry = WorkflowRegistry()

    register_instagram_automation_handlers(
        registry,
        instagram_connect=_connect(),
        workflow_factory=FakeAutomation,
        runtime_setup=lambda **kwargs: None,
    )

    assert set(registry.workflow_ids()) >= set(INSTAGRAM_AUTOMATION_WORKFLOW_IDS)
