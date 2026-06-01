"""Request validation for the TikTok Followers bridge runner."""

from dataclasses import dataclass
from typing import Any, Dict, List

from bridges.tiktok.runtime.ipc import send_error
from bridges.tiktok.workflows.automation.runtime.followers_planning import (
    build_target_list,
    has_empty_target_candidates,
)


@dataclass(frozen=True)
class FollowersWorkflowRequest:
    device_id: str
    bot_username: str | None
    target_list: List[str]


def validate_followers_workflow_request(config: Dict[str, Any]) -> FollowersWorkflowRequest | None:
    device_id = config.get("deviceId")
    bot_username = config.get("botUsername")

    if not device_id:
        send_error("No device ID provided")
        return None

    target_list = build_target_list(config)
    if not target_list:
        if has_empty_target_candidates(config):
            send_error("No valid targets provided")
        else:
            send_error("No target provided")
        return None

    return FollowersWorkflowRequest(
        device_id=device_id,
        bot_username=bot_username,
        target_list=target_list,
    )


__all__ = ["FollowersWorkflowRequest", "validate_followers_workflow_request"]
