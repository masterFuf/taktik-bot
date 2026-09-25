"""The one launcher of a TikTok scraping run, and its Agent handlers.

`run_tiktok_scraping` is what the desktop bridges call (`tiktok_scraping_bridge`, and the
`scraping` branch of the `tiktok_bridge` dispatcher) and what the handlers registered as
`tiktok.automation.scraping` and `tiktok.standalone.tiktok_scraping` (the CLI) call: read the
payload (`payload.py`), start TikTok, scrape, file the session and its profiles. What differs
between hosts is injected:
- `tiktok_startup() -> TikTokStartup`: clean restart, language, account; supplies the device.
  Without it the injected `device` is used as is.
- `notifier`: where the live events and statuses go (the bridge's stdout IPC; the log otherwise).
- `workflow_hook(workflow)`: registers the workflow for a stop signal.
No injected callable receives the whole payload, so the app's config contract test can still see
every key the bot reads.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Callable, Mapping, Optional

from loguru import logger

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    merge_invocation_payload,
    notify,
)
from taktik.core.social_media.tiktok.actions.business.workflows.scraping.payload import (
    save_to_db_from_payload,
    scraping_config_from_payload,
    scraping_source,
)


TIKTOK_AUTOMATION_SCRAPING_WORKFLOW_ID = "tiktok.automation.scraping"
TIKTOK_STANDALONE_SCRAPING_WORKFLOW_ID = "tiktok.standalone.tiktok_scraping"
TIKTOK_SCRAPING_WORKFLOW_IDS = (
    TIKTOK_AUTOMATION_SCRAPING_WORKFLOW_ID,
    TIKTOK_STANDALONE_SCRAPING_WORKFLOW_ID,
)
ScrapingWorkflowFactory = Callable[..., Any]
NavigationFactory = Callable[[Any], Any]
StartupProvider = Callable[[], Any]
WorkflowHook = Callable[[Any], None]


def _default_workflow_factory() -> ScrapingWorkflowFactory:
    # Resolved at call time, so the module's class is the one a run gets.
    from taktik.core.social_media.tiktok.actions.business.workflows.scraping import workflow

    return workflow.ScrapingWorkflow


def _default_navigation_factory() -> NavigationFactory:
    from taktik.core.social_media.tiktok.actions.atomic.navigation import navigation_actions

    return navigation_actions.NavigationActions


def run_tiktok_scraping(
    payload: Mapping[str, Any],
    *,
    device=None,
    notifier=None,
    navigation_factory: Optional[NavigationFactory] = None,
    workflow_factory: Optional[ScrapingWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    workflow_hook: Optional[WorkflowHook] = None,
) -> dict[str, Any]:
    """Start, scrape the source a payload names, and file the session unless told not to."""
    from taktik.core.database import tiktok_scraping
    from taktik.core.social_media.tiktok.workflows.runtime.notifier import LoggingWorkflowNotifier

    notifier = notifier if notifier is not None else LoggingWorkflowNotifier()
    config = scraping_config_from_payload(payload)
    save_to_db = save_to_db_from_payload(payload)
    logger.info(
        f"Enrichment: {'enabled' if config.enrich_profiles else 'disabled'}, max: {config.max_profiles_to_enrich}"
    )

    run_device = device
    if tiktok_startup is not None:
        run_device = tiktok_startup().device

    navigation = (navigation_factory or _default_navigation_factory())(run_device)
    workflow = (workflow_factory or _default_workflow_factory())(run_device, navigation, config)
    if workflow_hook is not None:
        workflow_hook(workflow)

    session_id = tiktok_scraping.open_scraping_session(*scraping_source(config)) if save_to_db else None
    _attach_callbacks(workflow, notifier)
    if session_id:
        workflow.set_on_save_profile_callback(
            lambda profile: tiktok_scraping.save_scraped_profile(session_id, profile)
        )

    start_time = time.time()
    profiles = workflow.run()
    duration = int(time.time() - start_time)

    # The reason, not `workflow.stopped`: a spent session budget also answers "stopped", and a run
    # that went the distance it was given is a completed run, not an interrupted one.
    reason = workflow.completion_reason or "completed"
    if session_id:
        tiktok_scraping.close_scraping_session(
            session_id, len(profiles), "STOPPED" if reason == "stopped_by_user" else "COMPLETED", duration
        )

    notify(notifier, "scraping_completed", totalScraped=len(profiles))
    if reason == "max_duration_reached":
        message = (
            f"Maximum session duration reached ({config.session_duration_minutes:g} minutes): "
            f"scraped {len(profiles)} profiles"
        )
    else:
        message = f"Scraped {len(profiles)} profiles"
    notify(notifier, "status", status="completed", message=message)

    return {
        "success": True,
        "profiles": profiles,
        "total_scraped": len(profiles),
        "completion_reason": reason,
        "session_id": session_id,
        "stats": workflow.stats.to_dict(),
    }


def build_tiktok_scraping_handler(
    *,
    device,
    notifier=None,
    navigation_factory: Optional[NavigationFactory] = None,
    workflow_factory: Optional[ScrapingWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
) -> WorkflowHandler:
    """Build the scraping handler: the same launcher as the desktop bridges."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        return run_tiktok_scraping(
            merge_invocation_payload(invocation, payload),
            device=device,
            notifier=notifier,
            navigation_factory=navigation_factory,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
        )

    return handler


def register_tiktok_scraping_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    notifier=None,
    navigation_factory: Optional[NavigationFactory] = None,
    workflow_factory: Optional[ScrapingWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
) -> WorkflowRegistry:
    """Register TikTok scraping handlers into an injected Agent registry."""
    handler = build_tiktok_scraping_handler(
        device=device,
        notifier=notifier,
        navigation_factory=navigation_factory,
        workflow_factory=workflow_factory,
        tiktok_startup=tiktok_startup,
    )
    for workflow_id in TIKTOK_SCRAPING_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _attach_callbacks(workflow: Any, notifier: Any) -> None:
    """Forward the scraping callbacks to the notifier, as stdout events on the desktop."""
    workflow.set_on_status_callback(
        lambda status, message: notify(notifier, "status", status=status, message=message)
    )
    workflow.set_on_progress_callback(
        lambda scraped, total, current: notify(
            notifier, "scraping_progress", scraped=scraped, total=total, current=current
        )
    )
    workflow.set_on_profile_callback(
        lambda profile: notify(
            notifier,
            "scraping_profile",
            username=profile.get("username", ""),
            followersCount=profile.get("followers_count", 0),
            followingCount=profile.get("following_count", 0),
            scrapedAt=datetime.now().isoformat(),
        )
    )
    workflow.set_on_error_callback(lambda message: notify(notifier, "error", error=message))


__all__ = [
    "TIKTOK_AUTOMATION_SCRAPING_WORKFLOW_ID",
    "TIKTOK_SCRAPING_WORKFLOW_IDS",
    "TIKTOK_STANDALONE_SCRAPING_WORKFLOW_ID",
    "build_tiktok_scraping_handler",
    "register_tiktok_scraping_handlers",
    "run_tiktok_scraping",
]
