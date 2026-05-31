"""Agent runtime handler for TikTok scraping workflows."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.atomic.navigation_actions import NavigationActions
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    bool_param,
    int_param,
    list_param,
    merge_invocation_payload,
    notify,
)
from taktik.core.social_media.tiktok.actions.business.workflows.scraping.models import ScrapingConfig
from taktik.core.social_media.tiktok.actions.business.workflows.scraping.workflow import ScrapingWorkflow


TIKTOK_AUTOMATION_SCRAPING_WORKFLOW_ID = "tiktok.automation.scraping"
TIKTOK_STANDALONE_SCRAPING_WORKFLOW_ID = "tiktok.standalone.tiktok_scraping"
TIKTOK_SCRAPING_WORKFLOW_IDS = (
    TIKTOK_AUTOMATION_SCRAPING_WORKFLOW_ID,
    TIKTOK_STANDALONE_SCRAPING_WORKFLOW_ID,
)
ScrapingWorkflowFactory = Callable[..., Any]
NavigationFactory = Callable[[Any], Any]
ProfileSink = Callable[[dict[str, Any]], None]


def build_tiktok_scraping_handler(
    *,
    device,
    notifier=None,
    profile_sink: ProfileSink | None = None,
    navigation_factory: NavigationFactory = NavigationActions,
    workflow_factory: ScrapingWorkflowFactory = ScrapingWorkflow,
) -> WorkflowHandler:
    """Build an injectable scraping handler without owning DB persistence."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = merge_invocation_payload(invocation, payload)
        workflow = workflow_factory(device, navigation_factory(device), _scraping_config(merged))
        _attach_callbacks(workflow, notifier, profile_sink=profile_sink)
        profiles = workflow.run()
        return {
            "success": True,
            "profiles": profiles,
            "total_scraped": len(profiles),
            "stats": workflow.stats.to_dict(),
        }

    return handler


def register_tiktok_scraping_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    notifier=None,
    profile_sink: ProfileSink | None = None,
    navigation_factory: NavigationFactory = NavigationActions,
    workflow_factory: ScrapingWorkflowFactory = ScrapingWorkflow,
) -> WorkflowRegistry:
    """Register TikTok scraping handlers into an injected Agent registry."""
    handler = build_tiktok_scraping_handler(
        device=device,
        notifier=notifier,
        profile_sink=profile_sink,
        navigation_factory=navigation_factory,
        workflow_factory=workflow_factory,
    )
    for workflow_id in TIKTOK_SCRAPING_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _scraping_config(payload: Mapping[str, Any]) -> ScrapingConfig:
    scrape_type = str(payload.get("type") or payload.get("scrape_type") or "target").strip().lower()
    target_scrape_type = str(
        payload.get("scrapeType") or payload.get("target_scrape_type") or "followers"
    ).strip().lower()
    target_usernames = list_param(payload, "target_usernames", "targetUsernames")
    hashtag = str(payload.get("hashtag") or "").strip().lstrip("#")

    if scrape_type == "target" and not target_usernames:
        raise ValueError("TikTok scraping requires targetUsernames for target scraping")
    if scrape_type == "hashtag" and not hashtag:
        raise ValueError("TikTok scraping requires a non-empty hashtag for hashtag scraping")

    return ScrapingConfig(
        scrape_type=scrape_type,
        target_usernames=target_usernames,
        target_scrape_type=target_scrape_type,
        hashtag=hashtag,
        max_profiles=int_param(payload, "max_profiles", "maxProfiles", default=500),
        max_videos=int_param(payload, "max_videos", "maxVideos", "maxPosts", default=50),
        enrich_profiles=bool_param(payload, "enrich_profiles", "enrichProfiles", default=True),
        max_profiles_to_enrich=int_param(
            payload, "max_profiles_to_enrich", "maxProfilesToEnrich", default=50
        ),
    )


def _attach_callbacks(workflow: Any, notifier: Any, *, profile_sink: ProfileSink | None) -> None:
    if notifier is not None:
        if hasattr(workflow, "set_on_status_callback"):
            workflow.set_on_status_callback(
                lambda status, message: notify(
                    notifier, "status", status=status, message=message
                )
            )
        if hasattr(workflow, "set_on_progress_callback"):
            workflow.set_on_progress_callback(
                lambda scraped, total, current: notify(
                    notifier,
                    "scraping_progress",
                    scraped=scraped,
                    total=total,
                    current=current,
                )
            )
        if hasattr(workflow, "set_on_profile_callback"):
            workflow.set_on_profile_callback(
                lambda profile: notify(notifier, "scraping_profile", profile=profile)
            )
        if hasattr(workflow, "set_on_error_callback"):
            workflow.set_on_error_callback(lambda message: notify(notifier, "error", message=message))

    if profile_sink is not None and hasattr(workflow, "set_on_save_profile_callback"):
        workflow.set_on_save_profile_callback(profile_sink)
