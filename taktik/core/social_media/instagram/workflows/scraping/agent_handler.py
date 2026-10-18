"""The one launcher of an Instagram scraping run, and its Agent handlers.

`run_instagram_scraping` is what the desktop bridge (`scraping_bridge`) calls and what the handlers
registered as `instagram.scraping.<type>` (the CLI) call: read the payload (`payload.py`, whose
reader refuses a setting out of its bounds and a run with nothing to scrape), then ask the host for
the phone, start Instagram when the host restarts it, match the selectors to the phone (installed
version, app language: `runtime_setup.prepare_instagram_selectors`, the automation launcher's),
then run `ScrapingWorkflow`. The order is the launcher's, for every host: what the reader refuses
never reaches the phone. What differs between the hosts is injected:
- `connect(package_name) -> InstagramRunPhone`: the phone, on the Instagram the payload names
  (`packageName`), connected by the host in this call (the desktop: its database and its
  connection; the CLI: its connection). Its `start` is a clean restart before the run: the desktop
  restarts Instagram itself before it launches the bridge, so the bridge gives none. Its
  `installed_version` is the version the selector overrides are chosen for.
- `ai_notifier`: where the AI qualification reports (the bridge's stdout IPC).
- `instagram_scraping_ai_service(**kwargs)`: builds the AI service the run asks for.
- `instagram_ai_key() -> str | None`: the OpenRouter key when the payload brings none (the CLI's
  environment).
No injected callable receives the whole payload, so the app's config contract test can still see
every key the bot reads.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from loguru import logger

from taktik.core.kernel.contracts import WorkflowInvocation
from taktik.core.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.instagram.workflows.common.startup import InstagramConnect
from taktik.core.social_media.instagram.workflows.scraping.payload import (
    INSTAGRAM_SCRAPING_TYPES,
    scraping_config_from_payload,
)


INSTAGRAM_SCRAPING_TARGET_WORKFLOW_ID = "instagram.scraping.target"
INSTAGRAM_SCRAPING_HASHTAG_WORKFLOW_ID = "instagram.scraping.hashtag"
INSTAGRAM_SCRAPING_POST_URL_WORKFLOW_ID = "instagram.scraping.post_url"
INSTAGRAM_SCRAPING_USERNAMES_WORKFLOW_ID = "instagram.scraping.usernames"
INSTAGRAM_SCRAPING_PROFILE_POSTS_WORKFLOW_ID = "instagram.scraping.profile_posts"
INSTAGRAM_SCRAPING_WORKFLOW_IDS = tuple(f"instagram.scraping.{kind}" for kind in INSTAGRAM_SCRAPING_TYPES)

ScrapingWorkflowFactory = Callable[..., Any]
AIServiceFactory = Callable[..., Any]
AIKeyProvider = Callable[[], Optional[str]]


def _default_workflow_factory() -> ScrapingWorkflowFactory:
    # Resolved at call time, so the module's class is the one a run gets.
    from taktik.core.social_media.instagram.workflows.scraping import scraping_workflow

    return scraping_workflow.ScrapingWorkflow


def run_instagram_scraping(
    payload: Mapping[str, Any],
    *,
    connect: InstagramConnect,
    ai_notifier=None,
    instagram_scraping_ai_service: Optional[AIServiceFactory] = None,
    instagram_ai_key: Optional[AIKeyProvider] = None,
    workflow_factory: Optional[ScrapingWorkflowFactory] = None,
) -> dict[str, Any]:
    """Read the payload, ask the host for the phone, start Instagram when the host restarts it, match
    the selectors to the phone, then scrape the source the payload names."""
    # Resolved at call time, so a run gets the modules' current objects.
    from taktik.core.social_media.instagram.workflows.common import runtime_setup
    from taktik.core.social_media.instagram.workflows.common.startup import (
        InstagramStartError,
        _log_to_logger,
    )

    # Read and validated before the host touches the phone: what the reader refuses never reaches it.
    scraping_config = scraping_config_from_payload(payload)
    phone = connect(payload.get("packageName"))

    if phone.start is not None and not phone.start():
        raise InstagramStartError("Instagram did not start cleanly; the scraping was not started")

    if scraping_config.get('ai_mode') and not scraping_config.get('openrouter_api_key') and instagram_ai_key:
        key = instagram_ai_key()
        if key:
            scraping_config['openrouter_api_key'] = key

    logger.info(f"Starting scraping workflow: {scraping_config['type']}")
    if scraping_config.get('enrich_profiles', False):
        logger.info("Enriched scraping enabled - will visit each profile for details")
    if scraping_config.get('deep_qualify', False):
        logger.info(
            f"\U0001f52c Deep qualify enabled — "
            f"max_following={scraping_config.get('deep_qualify_max_following', 30)}"
        )
    else:
        logger.info(
            f"\U0001f52c Deep qualify OFF — config received "
            f"deepQualify={payload.get('deepQualify')!r}, "
            f"enrichProfiles={payload.get('enrichProfiles')!r}"
        )

    # Before the workflow is built: a phone in another language or on another version must not
    # be read with the baseline's selectors.
    runtime_setup.prepare_instagram_selectors(
        device=getattr(phone.device_manager, "device", None),
        installed_version_provider=phone.installed_version,
        log=_log_to_logger,
    )

    workflow = (workflow_factory or _default_workflow_factory())(
        phone.device_manager,
        scraping_config,
        ai_notifier=ai_notifier,
        ai_service_factory=instagram_scraping_ai_service,
    )
    return workflow.run()


def instagram_scraping_payload(invocation: WorkflowInvocation, payload: Mapping[str, Any]) -> dict[str, Any]:
    """The payload a handler call stands for: every key kept, the source type the id names."""
    merged = dict(payload)
    merged.update(invocation.params)
    merged["type"] = _scraping_type_from_id(invocation.workflow_id)
    return merged


def build_instagram_scraping_handler(
    *,
    instagram_connect: Optional[InstagramConnect] = None,
    ai_notifier=None,
    instagram_scraping_ai_service: Optional[AIServiceFactory] = None,
    instagram_ai_key: Optional[AIKeyProvider] = None,
    workflow_factory: Optional[ScrapingWorkflowFactory] = None,
) -> WorkflowHandler:
    """Build an injectable scraping handler: the launcher, on the phone the host connects."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        if instagram_connect is None:
            raise RuntimeError("Instagram scraping needs a host that connects the phone")
        return run_instagram_scraping(
            instagram_scraping_payload(invocation, payload),
            connect=instagram_connect,
            ai_notifier=ai_notifier,
            instagram_scraping_ai_service=instagram_scraping_ai_service,
            instagram_ai_key=instagram_ai_key,
            workflow_factory=workflow_factory,
        )

    return handler


def register_instagram_scraping_handlers(
    registry: WorkflowRegistry,
    *,
    instagram_connect: Optional[InstagramConnect] = None,
    ai_notifier=None,
    instagram_scraping_ai_service: Optional[AIServiceFactory] = None,
    instagram_ai_key: Optional[AIKeyProvider] = None,
    workflow_factory: Optional[ScrapingWorkflowFactory] = None,
) -> WorkflowRegistry:
    """Register Instagram scraping handlers into an injected Agent registry."""
    handler = build_instagram_scraping_handler(
        instagram_connect=instagram_connect,
        ai_notifier=ai_notifier,
        instagram_scraping_ai_service=instagram_scraping_ai_service,
        instagram_ai_key=instagram_ai_key,
        workflow_factory=workflow_factory,
    )
    for workflow_id in INSTAGRAM_SCRAPING_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _scraping_type_from_id(workflow_id: str) -> str:
    prefix = "instagram.scraping."
    scraping_type = workflow_id[len(prefix):] if workflow_id.startswith(prefix) else ""
    if scraping_type not in INSTAGRAM_SCRAPING_TYPES:
        raise ValueError(f"Unsupported Instagram scraping workflow id: {workflow_id}")
    return scraping_type


__all__ = [
    "INSTAGRAM_SCRAPING_HASHTAG_WORKFLOW_ID",
    "INSTAGRAM_SCRAPING_POST_URL_WORKFLOW_ID",
    "INSTAGRAM_SCRAPING_PROFILE_POSTS_WORKFLOW_ID",
    "INSTAGRAM_SCRAPING_TARGET_WORKFLOW_ID",
    "INSTAGRAM_SCRAPING_USERNAMES_WORKFLOW_ID",
    "INSTAGRAM_SCRAPING_WORKFLOW_IDS",
    "build_instagram_scraping_handler",
    "instagram_scraping_payload",
    "register_instagram_scraping_handlers",
    "run_instagram_scraping",
]
