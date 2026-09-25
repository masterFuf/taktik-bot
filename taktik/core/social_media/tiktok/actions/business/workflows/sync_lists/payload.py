"""One reading of a TikTok follow-graph sync payload, for the bridge and the Agent handler alike.

The wire form is the page's camelCase (`TikTokSync.tsx`, and the scheduler's Sync node); the
snake_case names an Agent plan or a CLI call writes stay accepted. Every key is read by name, so
the app's config contract test can see which ones the bot reads.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from taktik.core.social_media.tiktok.actions.business.workflows._internal.video_payload import (
    as_bool,
    as_float,
    as_int,
    first_given,
)

from .models import SyncListsConfig

#: Workflow type (the bridge's `workflowType`, the CLI id's last part) -> which list(s) to read.
LIST_TYPE_BY_WORKFLOW = {
    "sync_following": "following",
    "sync_followers": "followers",
    "sync_lists": "both",
}
LIST_TYPES = ("following", "followers", "both")


def list_type_from_payload(payload: Mapping[str, Any], workflow_type: Optional[str] = None) -> str:
    """`listType` when it names a list, else the workflow type's list, else `following`.

    `workflow_type` defaults to the payload's `workflowType`. Never `both` by default: it would
    double the device time of a mislabelled run.
    """
    explicit = str(payload.get("listType") or payload.get("list_type") or "").strip().lower()
    if explicit in LIST_TYPES:
        return explicit
    if workflow_type is None:
        workflow_type = payload.get("workflowType")
    return LIST_TYPE_BY_WORKFLOW.get(workflow_type, "following")


def sync_config_from_payload(payload: Mapping[str, Any], list_type: str) -> SyncListsConfig:
    """The config of one sync run; an absent key keeps the page's default."""
    return SyncListsConfig(
        list_type=list_type,
        incremental=as_bool(payload.get("incremental"), True),
        max_scrolls=as_int(first_given(payload.get("maxScrolls"), payload.get("max_scrolls")), 60),
        resolve_missing_handles=as_bool(
            first_given(payload.get("resolveMissingHandles"), payload.get("resolve_missing_handles")), False
        ),
        max_resolutions=as_int(first_given(payload.get("maxResolutions"), payload.get("max_resolutions")), 50),
        min_delay=as_float(first_given(payload.get("minDelay"), payload.get("min_delay")), 0.6),
        max_delay=as_float(first_given(payload.get("maxDelay"), payload.get("max_delay")), 1.4),
    )


__all__ = ["LIST_TYPES", "LIST_TYPE_BY_WORKFLOW", "list_type_from_payload", "sync_config_from_payload"]
