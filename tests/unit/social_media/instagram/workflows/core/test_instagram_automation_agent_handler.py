import pytest

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowRegistry
from taktik.core.social_media.instagram.workflows.core.agent_handler import (
    INSTAGRAM_AUTOMATION_WORKFLOW_IDS,
    build_instagram_automation_handler,
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


class FakeDeviceManager:
    device = object()


def test_instagram_automation_handler_runs_workflow_with_bridge_config():
    runtime_calls = []
    ai_calls = []
    logs = []
    automations = []

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
        device_manager=FakeDeviceManager(),
        workflow_factory=workflow_factory,
        runtime_setup=runtime_setup,
        ai_hook_installer=lambda **kwargs: ai_calls.append(kwargs),
        ai_service_factory=ai_service_factory,
        installed_version_provider=lambda: "321",
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

    assert result == {"success": True, "stats": {"likes": 2}}
    assert automations[0].ran is True
    assert runtime_calls[0]["workflow_config"]["actions"][0]["target_username"] == "alpha"
    assert runtime_calls[0]["package_name"] == "com.instagram.android.c1"
    assert runtime_calls[0]["installed_version_provider"]() == "321"
    assert ai_calls[0]["ai"] == {"api": "key"}
    assert ai_calls[0]["device"] is FakeDeviceManager.device
    assert logs == []


def test_instagram_automation_handler_defaults_feed_target():
    runtime_calls = []

    handler = build_instagram_automation_handler(
        device_manager=FakeDeviceManager(),
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
    handler = build_instagram_automation_handler(
        device_manager=FakeDeviceManager(),
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


def test_register_instagram_automation_handlers_registers_manifest_ids():
    registry = WorkflowRegistry()

    register_instagram_automation_handlers(
        registry,
        device_manager=FakeDeviceManager(),
        workflow_factory=FakeAutomation,
        runtime_setup=lambda **kwargs: None,
    )

    assert set(registry.workflow_ids()) >= set(INSTAGRAM_AUTOMATION_WORKFLOW_IDS)
