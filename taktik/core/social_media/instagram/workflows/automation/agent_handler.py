"""The one launcher of an Instagram automation run, and its Agent handlers.

`run_instagram_automation` is what the desktop bridge calls and what the handlers registered as
`instagram.automation.<type>` (the CLI) call. The payload is the page's config, read whole by
`build_instagram_automation_config`. The launcher holds the order for every host: read and
validate the payload, then ask the host for the phone, then restart Instagram and run. What differs
between the hosts is injected:
- `connect(package_name) -> InstagramRunPhone`: the phone, on the Instagram the payload names
  (`packageName`, a clone; None: the installed one), with the clean restart before the run
  (`startup.py`) and the installed version the selector overrides are chosen for. The host does
  everything that touches the phone in this call (the desktop: its connection, the IP rotation, the
  media capture; the CLI: its connection), so what the reader refuses never reaches the phone.
- `instagram_ai_service(ai_config) -> service | None`: the AI service the run asks for.
- `decision_provider`: the desktop's per-profile decision round trip, when the run asks for it.
- `reporter`: the host's live events (`config_built`, `running`, `finished`), all optional.
- `step_hook(step, run_step)`: wraps each workflow step; the Lab traces steps with it.
No injected callable receives the whole payload, so the app's config contract test can still see
every key the bot reads.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from taktik.core.kernel.contracts import WorkflowInvocation
from taktik.core.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.shared.device.network_door import open_network_door
from taktik.core.social_media.instagram.workflows.common.startup import (
    InstagramConnect,
    InstagramStartError,
    _log_to_logger,
    package_name_from_payload,
)


INSTAGRAM_AUTOMATION_WORKFLOW_TYPES = (
    "target_followers",
    "target_following",
    "target_profiles",
    "hashtags",
    "post_url",
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
_AUTO_TARGET_WORKFLOWS = {"feed", "unfollow", "sync_following", "sync_followers_following"}

InstagramAutomationFactory = Callable[..., Any]
RuntimeSetup = Callable[..., None]
AIHookInstaller = Callable[..., None]
AIServiceFactory = Callable[[Mapping[str, Any]], Any]
DecisionProvider = Callable[[Mapping[str, Any]], dict]
LogCallback = Callable[[str, str], None]
StepRunner = Callable[[Mapping[str, Any]], Any]
StepHook = Callable[[Mapping[str, Any], StepRunner], Any]


def _emit(reporter: Any, method: str, *args: Any) -> None:
    target = getattr(reporter, method, None)
    if callable(target):
        target(*args)


def _hook_steps(run: Any, step_hook: StepHook) -> None:
    runner = run.workflow_runner
    run_step = runner.run_workflow_step
    runner.run_workflow_step = lambda step: step_hook(step, run_step)


def run_instagram_automation(
    payload: Mapping[str, Any],
    *,
    connect: InstagramConnect,
    instagram_ai_service: Optional[AIServiceFactory] = None,
    decision_provider: Optional[DecisionProvider] = None,
    reporter: Any = None,
    log: Optional[LogCallback] = None,
    step_hook: Optional[StepHook] = None,
    workflow_factory: Optional[InstagramAutomationFactory] = None,
    runtime_setup: Optional[RuntimeSetup] = None,
    ai_hook_installer: Optional[AIHookInstaller] = None,
) -> dict[str, Any]:
    """Read the page payload, ask the host for the phone, open the network door, start Instagram, then
    configure, hook and run one automation session."""
    # Resolved at call time, so a run gets the modules' current objects.
    from taktik.core.social_media.instagram.workflows.common import ai_hooks, runtime_setup as setup
    from taktik.core.social_media.instagram.workflows.automation import automation
    from taktik.core.social_media.instagram.workflows.automation.config_builder import (
        build_instagram_automation_config,
    )

    # Without a host of its own (the CLI), the run's setup lines go to the log.
    log = log or _log_to_logger
    package_name = package_name_from_payload(payload)

    # Read and validated before the host touches the phone: what the reader refuses never reaches it.
    workflow_config = build_instagram_automation_config(payload)
    phone = connect(package_name)
    # A phone without network does not start its run, from any host (`NetworkUnreachableError`).
    open_network_door(payload.get("deviceId"))

    if phone.start is not None and not phone.start():
        raise InstagramStartError("Instagram did not start cleanly; the run was not started")

    _emit(reporter, "config_built", workflow_config)

    device_manager = phone.device_manager
    run = (workflow_factory or automation.InstagramAutomation)(device_manager)
    (runtime_setup or setup.prepare_instagram_automation_runtime)(
        automation=run,
        workflow_config=workflow_config,
        package_name=package_name,
        installed_version_provider=phone.installed_version,
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

    if step_hook is not None:
        _hook_steps(run, step_hook)

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
    target's aliases, `feed_stories`, `appLanguage` (`package_name` is read by the launcher, with every
    Instagram launcher: `package_name_from_payload`).
    """
    merged = dict(payload)
    merged.update(invocation.params)

    workflow_type = _workflow_type_from_id(invocation.workflow_id)
    merged["workflowType"] = workflow_type
    merged["target"] = _target_for_workflow(workflow_type, merged)
    _alias(merged, "feedStories", "feed_stories")
    _alias(merged, "language", "appLanguage")
    if not str(merged.get("language") or "").strip():
        merged["language"] = "en"
    return merged


def build_instagram_automation_handler(
    *,
    instagram_connect: Optional[InstagramConnect] = None,
    instagram_ai_service: Optional[AIServiceFactory] = None,
    workflow_factory: Optional[InstagramAutomationFactory] = None,
    runtime_setup: Optional[RuntimeSetup] = None,
    ai_hook_installer: Optional[AIHookInstaller] = None,
    log: Optional[LogCallback] = None,
) -> WorkflowHandler:
    """Build an injectable automation handler: the launcher, on the phone the host connects."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        if instagram_connect is None:
            raise RuntimeError("Instagram automation needs a host that connects the phone")
        return run_instagram_automation(
            instagram_automation_payload(invocation, payload),
            connect=instagram_connect,
            instagram_ai_service=instagram_ai_service,
            log=log,
            workflow_factory=workflow_factory,
            runtime_setup=runtime_setup,
            ai_hook_installer=ai_hook_installer,
        )

    return handler


def register_instagram_automation_handlers(
    registry: WorkflowRegistry,
    *,
    instagram_connect: Optional[InstagramConnect] = None,
    instagram_ai_service: Optional[AIServiceFactory] = None,
    workflow_factory: Optional[InstagramAutomationFactory] = None,
    runtime_setup: Optional[RuntimeSetup] = None,
    ai_hook_installer: Optional[AIHookInstaller] = None,
    log: Optional[LogCallback] = None,
) -> WorkflowRegistry:
    """Register Instagram automation handlers into an injected Agent registry."""
    handler = build_instagram_automation_handler(
        instagram_connect=instagram_connect,
        instagram_ai_service=instagram_ai_service,
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
    "build_instagram_automation_handler",
    "instagram_automation_payload",
    "register_instagram_automation_handlers",
    "run_instagram_automation",
]
