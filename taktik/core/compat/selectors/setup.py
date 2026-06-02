"""Selector compatibility setup owners."""

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger

from .registry import VersionedSelectorRegistry, build_full_selector_map

from ...social_media.instagram.ui.selectors import (
    AUTH_SELECTORS as IG_AUTH,
    NAVIGATION_SELECTORS as IG_NAVIGATION,
    BUTTON_SELECTORS as IG_BUTTONS,
    PROFILE_SELECTORS as IG_PROFILE,
    POST_SELECTORS as IG_POST,
    STORY_SELECTORS as IG_STORY,
    DM_SELECTORS as IG_DM,
    POPUP_SELECTORS as IG_POPUP,
    SCROLL_SELECTORS as IG_SCROLL,
    DETECTION_SELECTORS as IG_DETECTION,
    TEXT_INPUT_SELECTORS as IG_TEXT_INPUT,
    PROBLEMATIC_PAGE_SELECTORS as IG_PROBLEMATIC,
    CONTENT_CREATION_SELECTORS as IG_CONTENT,
    FEED_SELECTORS as IG_FEED,
    UNFOLLOW_SELECTORS as IG_UNFOLLOW,
    NOTIFICATION_SELECTORS as IG_NOTIFICATION,
    HASHTAG_SELECTORS as IG_HASHTAG,
    FOLLOWERS_LIST_SELECTORS as IG_FOLLOWERS_LIST,
)
from ...social_media.tiktok.ui.selectors import (
    AUTH_SELECTORS as TT_AUTH,
    SIGNUP_SELECTORS as TT_SIGNUP,
    LOGOUT_SELECTORS as TT_LOGOUT,
    COUNTRY_PICKER_SELECTORS as TT_COUNTRY_PICKER,
    NAVIGATION_SELECTORS as TT_NAVIGATION,
    PROFILE_SELECTORS as TT_PROFILE,
    VIDEO_SELECTORS as TT_VIDEO,
    COMMENT_SELECTORS as TT_COMMENT,
    SEARCH_SELECTORS as TT_SEARCH,
    INBOX_SELECTORS as TT_INBOX,
    CONVERSATION_SELECTORS as TT_CONVERSATION,
    POPUP_SELECTORS as TT_POPUP,
    SCROLL_SELECTORS as TT_SCROLL,
    DETECTION_SELECTORS as TT_DETECTION,
    FOLLOWERS_SELECTORS as TT_FOLLOWERS,
)

INSTAGRAM_TARGET_VERSION = "410.0.0.53.71"
TIKTOK_TARGET_VERSION = "43.1.4"

INSTAGRAM_SELECTOR_DOMAINS = {
    "auth": IG_AUTH,
    "navigation": IG_NAVIGATION,
    "buttons": IG_BUTTONS,
    "profile": IG_PROFILE,
    "post": IG_POST,
    "story": IG_STORY,
    "dm": IG_DM,
    "popup": IG_POPUP,
    "scroll": IG_SCROLL,
    "detection": IG_DETECTION,
    "text_input": IG_TEXT_INPUT,
    "problematic_page": IG_PROBLEMATIC,
    "content": IG_CONTENT,
    "feed": IG_FEED,
    "unfollow": IG_UNFOLLOW,
    "notification": IG_NOTIFICATION,
    "hashtag": IG_HASHTAG,
    "followers_list": IG_FOLLOWERS_LIST,
}

TIKTOK_SELECTOR_DOMAINS = {
    "auth": TT_AUTH,
    "signup": TT_SIGNUP,
    "logout": TT_LOGOUT,
    "country_picker": TT_COUNTRY_PICKER,
    "navigation": TT_NAVIGATION,
    "profile": TT_PROFILE,
    "video": TT_VIDEO,
    "comment": TT_COMMENT,
    "search": TT_SEARCH,
    "inbox": TT_INBOX,
    "conversation": TT_CONVERSATION,
    "popup": TT_POPUP,
    "scroll": TT_SCROLL,
    "detection": TT_DETECTION,
    "followers": TT_FOLLOWERS,
}


def create_registry(overrides_dir: Optional[str] = None) -> VersionedSelectorRegistry:
    """Create and return a fully initialized VersionedSelectorRegistry."""
    registry = VersionedSelectorRegistry(overrides_dir=overrides_dir)
    ig_map = build_full_selector_map(INSTAGRAM_SELECTOR_DOMAINS)
    tt_map = build_full_selector_map(TIKTOK_SELECTOR_DOMAINS)
    registry.register_app("instagram", ig_map, INSTAGRAM_TARGET_VERSION)
    registry.register_app("tiktok", tt_map, TIKTOK_TARGET_VERSION)
    logger.info(
        f"[Compat] Registry ready: "
        f"Instagram={len(ig_map)} selectors, "
        f"TikTok={len(tt_map)} selectors"
    )
    return registry


def build_xpath_to_selector_id_index(
    app: str, overrides_dir: Optional[str] = None
) -> Dict[str, str]:
    """Reverse index raw XPath -> logical selectorId for one app.

    Only XPaths that resolve to exactly one logical selectorId (namespaced
    ``domain.field``) are kept. XPaths shared by several selectors are dropped so
    callers never receive an ambiguous id. Dynamically generated XPaths (built
    from runtime parameters) are not in the catalogs and simply do not match.
    """
    registry = create_registry(overrides_dir=overrides_dir)
    version = registry.get_current_version(app) or ""
    candidates: Dict[str, set] = {}
    for selector_id, entry in registry.get_all(app, version).items():
        for xpath in entry.xpaths:
            candidates.setdefault(xpath, set()).add(selector_id)
    return {
        xpath: next(iter(ids))
        for xpath, ids in candidates.items()
        if len(ids) == 1
    }


def _load_yaml_overrides(app: str, overrides_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Load and return the raw YAML data for an app override file."""
    base_dir = overrides_dir or (Path(__file__).resolve().parent.parent / "data" / "overrides")
    override_path = base_dir / f"{app}.yaml"
    if not override_path.exists():
        return {}
    try:
        with open(override_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"[Compat] Failed to load {override_path}: {e}")
        return {}


def _resolve_overrides_for_version(
    data: Dict[str, Any], target_version: str
) -> Dict[str, List[str]]:
    """Resolve which overrides apply for *target_version*."""
    versions = data.get("versions", {})
    if not versions or isinstance(versions, str):
        return {}

    applicable = sorted(v for v in versions if str(v) <= target_version)

    merged: Dict[str, List[str]] = {}
    for version in applicable:
        entries = versions[version]
        if not isinstance(entries, dict):
            continue
        for action_key, xpaths in entries.items():
            if isinstance(xpaths, list):
                merged[action_key] = xpaths
            elif isinstance(xpaths, str):
                merged[action_key] = [xpaths]
    return merged


def _patch_singleton(
    domain_name: str,
    singleton: Any,
    overrides: Dict[str, List[str]],
) -> int:
    """Patch a dataclass singleton's fields in place."""
    prefix = f"{domain_name}."
    patched = 0

    for action_key, xpaths in overrides.items():
        if not action_key.startswith(prefix):
            continue
        field_name = action_key[len(prefix):]

        if not hasattr(singleton, field_name):
            logger.warning(
                f"[Compat] Override {action_key}: field '{field_name}' "
                f"not found on {type(singleton).__name__}, skipping"
            )
            continue

        current = getattr(singleton, field_name)
        if isinstance(current, list):
            setattr(singleton, field_name, xpaths)
        elif isinstance(current, str):
            setattr(singleton, field_name, xpaths[0] if xpaths else current)
        else:
            logger.warning(
                f"[Compat] Override {action_key}: unexpected type "
                f"{type(current).__name__}, skipping"
            )
            continue

        patched += 1
        logger.debug(f"[Compat] Patched {action_key} ({len(xpaths)} xpath(s))")

    return patched


def apply_version_overrides(
    app: str,
    detected_version: str,
    overrides_dir: Optional[str] = None,
) -> int:
    """Patch selector singletons in place for the detected app version."""
    domain_map = {
        "instagram": INSTAGRAM_SELECTOR_DOMAINS,
        "tiktok": TIKTOK_SELECTOR_DOMAINS,
    }

    if app not in domain_map:
        logger.error(f"[Compat] Unknown app: {app}")
        return 0

    baseline = {
        "instagram": INSTAGRAM_TARGET_VERSION,
        "tiktok": TIKTOK_TARGET_VERSION,
    }[app]

    if detected_version == baseline:
        logger.info(
            f"[Compat] {app} v{detected_version} matches baseline "
            f"v{baseline}, no overrides needed"
        )
        return 0

    base_dir = Path(overrides_dir) if overrides_dir else None
    data = _load_yaml_overrides(app, base_dir)
    if not data:
        logger.info(f"[Compat] No override file for {app}, using baseline selectors")
        return 0

    overrides = _resolve_overrides_for_version(data, detected_version)
    if not overrides:
        logger.info(f"[Compat] No applicable overrides for {app} v{detected_version}")
        return 0

    domains = domain_map[app]
    total_patched = 0
    for domain_name, singleton in domains.items():
        total_patched += _patch_singleton(domain_name, singleton, overrides)

    logger.info(
        f"[Compat] Applied {total_patched} selector override(s) "
        f"for {app} v{detected_version} (baseline: v{baseline})"
    )
    return total_patched
