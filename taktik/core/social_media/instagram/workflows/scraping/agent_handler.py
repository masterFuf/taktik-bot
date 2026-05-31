"""Agent runtime handlers for Instagram scraping workflows."""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping, Sequence

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.instagram.workflows.scraping.scraping_workflow import (
    ScrapingWorkflow,
)


INSTAGRAM_SCRAPING_TARGET_WORKFLOW_ID = "instagram.scraping.target"
INSTAGRAM_SCRAPING_HASHTAG_WORKFLOW_ID = "instagram.scraping.hashtag"
INSTAGRAM_SCRAPING_POST_URL_WORKFLOW_ID = "instagram.scraping.post_url"
INSTAGRAM_SCRAPING_WORKFLOW_IDS = (
    INSTAGRAM_SCRAPING_TARGET_WORKFLOW_ID,
    INSTAGRAM_SCRAPING_HASHTAG_WORKFLOW_ID,
    INSTAGRAM_SCRAPING_POST_URL_WORKFLOW_ID,
)
ScrapingWorkflowFactory = Callable[..., Any]


def build_instagram_scraping_handler(
    *,
    device_manager,
    ai_notifier=None,
    ai_service_factory=None,
    workflow_factory: ScrapingWorkflowFactory = ScrapingWorkflow,
) -> WorkflowHandler:
    """Build an injectable scraping handler without owning device connection."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        config = _scraping_config(invocation, payload)
        workflow = workflow_factory(
            device_manager,
            config,
            ai_notifier=ai_notifier,
            ai_service_factory=ai_service_factory,
        )
        return workflow.run()

    return handler


def register_instagram_scraping_handlers(
    registry: WorkflowRegistry,
    *,
    device_manager,
    ai_notifier=None,
    ai_service_factory=None,
    workflow_factory: ScrapingWorkflowFactory = ScrapingWorkflow,
) -> WorkflowRegistry:
    """Register Instagram scraping handlers into an injected Agent registry."""
    handler = build_instagram_scraping_handler(
        device_manager=device_manager,
        ai_notifier=ai_notifier,
        ai_service_factory=ai_service_factory,
        workflow_factory=workflow_factory,
    )
    for workflow_id in INSTAGRAM_SCRAPING_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _scraping_config(invocation: WorkflowInvocation, payload: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(payload)
    merged.update(invocation.params)

    if invocation.workflow_id == INSTAGRAM_SCRAPING_TARGET_WORKFLOW_ID:
        scraping_type = "target"
    elif invocation.workflow_id == INSTAGRAM_SCRAPING_HASHTAG_WORKFLOW_ID:
        scraping_type = "hashtag"
    elif invocation.workflow_id == INSTAGRAM_SCRAPING_POST_URL_WORKFLOW_ID:
        scraping_type = "post_url"
    else:
        raise ValueError(f"Unsupported Instagram scraping workflow id: {invocation.workflow_id}")

    config: dict[str, Any] = {
        "type": scraping_type,
        "session_duration_minutes": _int_param(
            merged,
            "session_duration_minutes",
            "sessionDurationMinutes",
            default=60,
        ),
        "max_profiles": _int_param(merged, "max_profiles", "maxProfiles", default=500),
        "export_csv": _bool_param(merged, "export_csv", "exportCsv", default=True),
        "save_to_db": _bool_param(merged, "save_to_db", "saveToDb", default=True),
        "enrich_profiles": _bool_param(
            merged,
            "enrich_profiles",
            "enrichProfiles",
            default=False,
        ),
        "response_language": _string_param(merged, "response_language", "appLanguage", default="en"),
    }

    rescrape_after_days = _value_param(merged, "rescrape_after_days", "rescrapeAfterDays")
    if rescrape_after_days is not None:
        config["rescrape_after_days"] = int(rescrape_after_days)

    if _bool_param(merged, "deep_qualify", "deepQualify", default=False):
        config["deep_qualify"] = True
        dq_max = _value_param(merged, "deep_qualify_max_following", "deepQualifyMaxFollowing")
        if dq_max is not None:
            config["deep_qualify_max_following"] = int(dq_max)

    if scraping_type == "target":
        _apply_target_config(config, merged)
    elif scraping_type == "hashtag":
        _apply_hashtag_config(config, merged)
    else:
        _apply_post_url_config(config, merged)

    _apply_ai_config(config, merged)
    return config


def _apply_target_config(config: dict[str, Any], payload: Mapping[str, Any]) -> None:
    targets = _list_param(payload, "target_usernames", "targetUsernames", "targets", "targetAccounts")
    if not targets:
        raise ValueError("Instagram target scraping requires targetUsernames")
    config["target_usernames"] = targets
    config["scrape_type"] = _string_param(payload, "scrape_type", "scrapeType", default="followers")
    config["scrape_post_likers"] = _bool_param(
        payload,
        "scrape_post_likers",
        "scrapePostLikers",
        default=True,
    )
    config["scrape_post_commenters"] = _bool_param(
        payload,
        "scrape_post_commenters",
        "scrapePostCommenters",
        default=False,
    )


def _apply_hashtag_config(config: dict[str, Any], payload: Mapping[str, Any]) -> None:
    hashtags = _list_param(payload, "hashtags", "hashtag")
    if not hashtags:
        raise ValueError("Instagram hashtag scraping requires hashtags")
    config["hashtags"] = hashtags
    config["hashtag"] = hashtags[0]
    config["scrape_likers"] = _bool_param(payload, "scrape_likers", "scrapeHashtagLikers", default=True)
    config["scrape_commenters"] = _bool_param(
        payload,
        "scrape_commenters",
        "scrapeHashtagCommenters",
        default=False,
    )
    config["max_posts"] = _int_param(payload, "max_posts", "maxPosts", default=50)


def _apply_post_url_config(config: dict[str, Any], payload: Mapping[str, Any]) -> None:
    post_urls = _list_param(payload, "post_urls", "postUrls", "postUrl")
    if not post_urls:
        raise ValueError("Instagram post_url scraping requires postUrls")
    config["post_urls"] = post_urls
    config["post_url"] = post_urls[0]
    config["scrape_likers"] = _bool_param(payload, "scrape_likers", "scrapePostUrlLikers", default=True)
    config["scrape_commenters"] = _bool_param(
        payload,
        "scrape_commenters",
        "scrapePostUrlCommenters",
        default=False,
    )
    config["post_id"] = _post_id_from_url(post_urls[0])


def _apply_ai_config(config: dict[str, Any], payload: Mapping[str, Any]) -> None:
    ai_config = payload.get("ai")
    if isinstance(ai_config, Mapping) and ai_config.get("enabled"):
        config["ai_mode"] = True
        config["ai_profile_analysis"] = ai_config.get("profileAnalysis", True)
        config["ai_niche"] = ai_config.get("niche", "")
        config["ai_qualification_prompt"] = ai_config.get("qualificationPrompt", "")
        config["openrouter_api_key"] = ai_config.get("openrouterApiKey", "")
        config["vision_model"] = ai_config.get("visionModel", "")
        config["ai_rescrape_mode"] = _string_param(payload, "ai_rescrape_mode", "aiRescrapeMode", default="full")
    else:
        config["ai_mode"] = _bool_param(payload, "ai_mode", "aiMode", default=False)


def _post_id_from_url(url: str) -> str:
    match = re.search(r"/p/([^/]+)/", url)
    if match:
        return match.group(1)
    match = re.search(r"/reel/([^/]+)/", url)
    return match.group(1) if match else "unknown"


def _value_param(payload: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    return None


def _string_param(payload: Mapping[str, Any], *names: str, default: str) -> str:
    value = _value_param(payload, *names)
    if value is None:
        return default
    return str(value).strip() or default


def _int_param(payload: Mapping[str, Any], *names: str, default: int) -> int:
    value = _value_param(payload, *names)
    if value is None:
        return default
    return int(value)


def _bool_param(payload: Mapping[str, Any], *names: str, default: bool) -> bool:
    value = _value_param(payload, *names)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _list_param(payload: Mapping[str, Any], *names: str) -> list[str]:
    value = _value_param(payload, *names)
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, Sequence):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []
