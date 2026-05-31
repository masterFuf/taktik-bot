"""Agent runtime handlers for Instagram automation workflows."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.instagram.workflows.core.ai_hooks import (
    install_instagram_ai_hooks,
)
from taktik.core.social_media.instagram.workflows.core.automation import (
    InstagramAutomation,
)
from taktik.core.social_media.instagram.workflows.core.config_builder import (
    build_instagram_automation_config,
)
from taktik.core.social_media.instagram.workflows.core.runtime_setup import (
    prepare_instagram_automation_runtime,
)


INSTAGRAM_AUTOMATION_WORKFLOW_TYPES = (
    "target_followers",
    "target_following",
    "hashtags",
    "post_url",
    "notifications",
    "unfollow",
    "feed",
    "sync_following",
    "sync_followers_following",
)
INSTAGRAM_AUTOMATION_WORKFLOW_IDS = tuple(
    f"instagram.automation.{workflow_type}"
    for workflow_type in INSTAGRAM_AUTOMATION_WORKFLOW_TYPES
)
InstagramAutomationFactory = Callable[..., Any]
RuntimeSetup = Callable[..., None]
AIHookInstaller = Callable[..., None]
AIServiceFactory = Callable[[Mapping[str, Any]], Any]
LogCallback = Callable[[str, str], None]


def build_instagram_automation_handler(
    *,
    device_manager,
    workflow_factory: InstagramAutomationFactory = InstagramAutomation,
    runtime_setup: RuntimeSetup = prepare_instagram_automation_runtime,
    ai_hook_installer: AIHookInstaller = install_instagram_ai_hooks,
    ai_service_factory: AIServiceFactory | None = None,
    installed_version_provider: Callable[[], str | None] | None = None,
    log: LogCallback | None = None,
) -> WorkflowHandler:
    """Build an injectable automation handler without owning bridge startup."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        raw_config = _automation_bridge_config(invocation, payload)
        workflow_config = build_instagram_automation_config(raw_config)
        automation = workflow_factory(device_manager)

        runtime_setup(
            automation=automation,
            workflow_config=workflow_config,
            package_name=raw_config.get("packageName"),
            installed_version_provider=installed_version_provider,
            log=log or _noop_log,
        )

        ai_config = raw_config.get("ai")
        if isinstance(ai_config, Mapping) and ai_config.get("enabled") and ai_service_factory:
            ai_service = ai_service_factory(ai_config)
            if ai_service:
                ai_hook_installer(
                    ai=ai_service,
                    ai_config=ai_config,
                    device=getattr(device_manager, "device", None),
                    language=raw_config.get("language", "en"),
                    log=log or _noop_log,
                )

        automation.run_workflow()
        return {
            "success": True,
            "stats": dict(getattr(automation, "stats", {})),
        }

    return handler


def register_instagram_automation_handlers(
    registry: WorkflowRegistry,
    *,
    device_manager,
    workflow_factory: InstagramAutomationFactory = InstagramAutomation,
    runtime_setup: RuntimeSetup = prepare_instagram_automation_runtime,
    ai_hook_installer: AIHookInstaller = install_instagram_ai_hooks,
    ai_service_factory: AIServiceFactory | None = None,
    installed_version_provider: Callable[[], str | None] | None = None,
    log: LogCallback | None = None,
) -> WorkflowRegistry:
    """Register Instagram automation handlers into an injected Agent registry."""
    handler = build_instagram_automation_handler(
        device_manager=device_manager,
        workflow_factory=workflow_factory,
        runtime_setup=runtime_setup,
        ai_hook_installer=ai_hook_installer,
        ai_service_factory=ai_service_factory,
        installed_version_provider=installed_version_provider,
        log=log,
    )
    for workflow_id in INSTAGRAM_AUTOMATION_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _automation_bridge_config(
    invocation: WorkflowInvocation,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(payload)
    merged.update(invocation.params)

    workflow_type = _workflow_type_from_id(invocation.workflow_id)
    target = _target_for_workflow(workflow_type, merged)

    config = {
        "workflowType": workflow_type,
        "target": target,
        "limits": _mapping_param(merged, "limits"),
        "probabilities": _mapping_param(merged, "probabilities"),
        "filters": _mapping_param(merged, "filters"),
        "session": _mapping_param(merged, "session"),
        "comments": _mapping_param(merged, "comments"),
        "feedStories": _mapping_param(merged, "feedStories", "feed_stories"),
        "unfollow": _mapping_param(merged, "unfollow"),
        "sync": _mapping_param(merged, "sync"),
        "ai": _mapping_param(merged, "ai"),
        "language": _string_param(merged, "language", "appLanguage", default="en"),
        "packageName": _value_param(merged, "packageName", "package_name"),
    }

    return {key: value for key, value in config.items() if value is not None}


def _workflow_type_from_id(workflow_id: str) -> str:
    prefix = "instagram.automation."
    if not workflow_id.startswith(prefix):
        raise ValueError(f"Unsupported Instagram automation workflow id: {workflow_id}")
    workflow_type = workflow_id[len(prefix):]
    if workflow_type not in INSTAGRAM_AUTOMATION_WORKFLOW_TYPES:
        raise ValueError(f"Unsupported Instagram automation workflow id: {workflow_id}")
    return workflow_type


def _target_for_workflow(workflow_type: str, payload: Mapping[str, Any]) -> str:
    value = _value_param(
        payload,
        "target",
        "targetUsername",
        "target_username",
        "username",
        "hashtag",
        "postUrl",
        "post_url",
    )
    if value is not None and str(value).strip():
        return str(value).strip()

    if workflow_type in {"feed", "notifications", "unfollow", "sync_following", "sync_followers_following"}:
        return workflow_type

    raise ValueError(f"Instagram automation workflow {workflow_type} requires target")


def _value_param(payload: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    return None


def _mapping_param(payload: Mapping[str, Any], *names: str) -> dict[str, Any]:
    value = _value_param(payload, *names)
    return dict(value) if isinstance(value, Mapping) else {}


def _string_param(payload: Mapping[str, Any], *names: str, default: str) -> str:
    value = _value_param(payload, *names)
    if value is None:
        return default
    return str(value).strip() or default


def _noop_log(_level: str, _message: str) -> None:
    return None
