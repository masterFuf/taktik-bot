"""The one launcher of an Instagram automation run, and its Agent handlers.

`run_instagram_automation` is what the desktop bridge calls and what the handlers registered as
`instagram.automation.<type>` (the CLI) call. The payload is the page's config, read whole by
`build_instagram_automation_config`. What differs between the hosts is injected:
- `instagram_start(package_name) -> bool`: the clean restart before the run (`startup.py`).
- `instagram_ai_service(ai_config) -> service | None`: the AI service the run asks for.
- `decision_provider`: the desktop's per-profile decision round trip, when the run asks for it.
- `instagram_installed_version() -> str | None`: the version the selector overrides are chosen for.
- `reporter`: the host's live events (`config_built`, `running`, `finished`), all optional.
No injected callable receives the whole payload, so the app's config contract test can still see
every key the bot reads.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry


INSTAGRAM_AUTOMATION_WORKFLOW_TYPES = (
    "target_followers",
    "target_following",
    "target_profiles",
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
#: Workflows whose target is the account itself: an absent target takes the workflow's name.
_AUTO_TARGET_WORKFLOWS = {"feed", "notifications", "unfollow", "sync_following", "sync_followers_following"}

InstagramAutomationFactory = Callable[..., Any]
RuntimeSetup = Callable[..., None]
AIHookInstaller = Callable[..., None]
InstagramStart = Callable[[Optional[str]], bool]
AIServiceFactory = Callable[[Mapping[str, Any]], Any]
DecisionProvider = Callable[[Mapping[str, Any]], dict]
VersionProvider = Callable[[], Optional[str]]
LogCallback = Callable[[str, str], None]


class InstagramStartError(RuntimeError):
    """Instagram could not be brought to a clean start; the run did not begin."""


def _log_to_logger(level: str, message: str) -> None:
    from loguru import logger

    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def _emit(reporter: Any, method: str, *args: Any) -> None:
    target = getattr(reporter, method, None)
    if callable(target):
        target(*args)


def run_instagram_automation(
    payload: Mapping[str, Any],
    *,
    device_manager,
    instagram_start: Optional[InstagramStart] = None,
    instagram_ai_service: Optional[AIServiceFactory] = None,
    decision_provider: Optional[DecisionProvider] = None,
    instagram_installed_version: Optional[VersionProvider] = None,
    reporter: Any = None,
    log: Optional[LogCallback] = None,
    workflow_factory: Optional[InstagramAutomationFactory] = None,
    runtime_setup: Optional[RuntimeSetup] = None,
    ai_hook_installer: Optional[AIHookInstaller] = None,
) -> dict[str, Any]:
    """Start Instagram, then configure, hook and run one automation session from a page payload."""
    # Resolved at call time, so a run gets the modules' current objects.
    from taktik.core.social_media.instagram.workflows.core import ai_hooks, automation, runtime_setup as setup
    from taktik.core.social_media.instagram.workflows.core.config_builder import (
        build_instagram_automation_config,
    )

    # Without a host of its own (the CLI), the run's setup lines go to the log.
    log = log or _log_to_logger
    package_name = payload.get("packageName")

    if instagram_start is not None and not instagram_start(package_name):
        raise InstagramStartError("Instagram did not start cleanly; the run was not started")

    workflow_config = build_instagram_automation_config(payload)
    _emit(reporter, "config_built", workflow_config)

    run = (workflow_factory or automation.InstagramAutomation)(device_manager)
    (runtime_setup or setup.prepare_instagram_automation_runtime)(
        automation=run,
        workflow_config=workflow_config,
        package_name=package_name,
        installed_version_provider=instagram_installed_version,
        log=log,
    )

    ai_config = payload.get("ai") or {}
    decision_mode = (ai_config.get("decision") or {}).get("mode") == "decide"
    ai_service = None
    if ai_config.get("enabled") and instagram_ai_service is not None:
        ai_service = instagram_ai_service(ai_config)
    if ai_service or decision_mode:
        (ai_hook_installer or ai_hooks.install_instagram_ai_hooks)(
            ai=ai_service,
            ai_config=ai_config,
            device=getattr(device_manager, "device", None),
            language=payload.get("language", "en"),
            log=log,
            decision_provider=decision_provider,
        )

    _emit(reporter, "running")
    run.run_workflow()
    # The session's totals, from the action ledger the session row is aggregated from.
    stats = run.final_stats()
    _emit(reporter, "finished", stats)
    return {"success": True, "stats": stats}


def instagram_automation_payload(
    invocation: WorkflowInvocation,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """The page payload a handler call stands for: every key kept, the id's workflow, a target.

    The handler used to copy eleven known sections and drop the rest, so the warmup caps, the
    pacing profile, the feed settings, the split between sources or the post URL's comment
    settings never reached a CLI run. Only the names a terminal user may type are added: the
    target's aliases, `feed_stories`, `appLanguage`, `package_name`.
    """
    merged = dict(payload)
    merged.update(invocation.params)

    workflow_type = _workflow_type_from_id(invocation.workflow_id)
    merged["workflowType"] = workflow_type
    merged["target"] = _target_for_workflow(workflow_type, merged)
    _alias(merged, "feedStories", "feed_stories")
    _alias(merged, "language", "appLanguage")
    _alias(merged, "packageName", "package_name")
    if not str(merged.get("language") or "").strip():
        merged["language"] = "en"
    return merged


def build_instagram_automation_handler(
    *,
    device_manager,
    instagram_start: Optional[InstagramStart] = None,
    instagram_ai_service: Optional[AIServiceFactory] = None,
    instagram_installed_version: Optional[VersionProvider] = None,
    workflow_factory: Optional[InstagramAutomationFactory] = None,
    runtime_setup: Optional[RuntimeSetup] = None,
    ai_hook_installer: Optional[AIHookInstaller] = None,
    log: Optional[LogCallback] = None,
) -> WorkflowHandler:
    """Build an injectable automation handler: the launcher, on the injected host."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        return run_instagram_automation(
            instagram_automation_payload(invocation, payload),
            device_manager=device_manager,
            instagram_start=instagram_start,
            instagram_ai_service=instagram_ai_service,
            instagram_installed_version=instagram_installed_version,
            log=log,
            workflow_factory=workflow_factory,
            runtime_setup=runtime_setup,
            ai_hook_installer=ai_hook_installer,
        )

    return handler


def register_instagram_automation_handlers(
    registry: WorkflowRegistry,
    *,
    device_manager,
    instagram_start: Optional[InstagramStart] = None,
    instagram_ai_service: Optional[AIServiceFactory] = None,
    instagram_installed_version: Optional[VersionProvider] = None,
    workflow_factory: Optional[InstagramAutomationFactory] = None,
    runtime_setup: Optional[RuntimeSetup] = None,
    ai_hook_installer: Optional[AIHookInstaller] = None,
    log: Optional[LogCallback] = None,
) -> WorkflowRegistry:
    """Register Instagram automation handlers into an injected Agent registry."""
    handler = build_instagram_automation_handler(
        device_manager=device_manager,
        instagram_start=instagram_start,
        instagram_ai_service=instagram_ai_service,
        instagram_installed_version=instagram_installed_version,
        workflow_factory=workflow_factory,
        runtime_setup=runtime_setup,
        ai_hook_installer=ai_hook_installer,
        log=log,
    )
    for workflow_id in INSTAGRAM_AUTOMATION_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


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

    if workflow_type in _AUTO_TARGET_WORKFLOWS:
        return workflow_type

    raise ValueError(f"Instagram automation workflow {workflow_type} requires target")


def _value_param(payload: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    return None


def _alias(payload: dict[str, Any], name: str, alias: str) -> None:
    if name not in payload and alias in payload:
        payload[name] = payload[alias]


__all__ = [
    "INSTAGRAM_AUTOMATION_WORKFLOW_IDS",
    "INSTAGRAM_AUTOMATION_WORKFLOW_TYPES",
    "InstagramStartError",
    "build_instagram_automation_handler",
    "instagram_automation_payload",
    "register_instagram_automation_handlers",
    "run_instagram_automation",
]
