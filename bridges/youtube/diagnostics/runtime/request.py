"""Request loading and validation for the YouTube action-test bridge."""

from dataclasses import dataclass

from bridges.youtube.diagnostics.runtime.events import emit
from bridges.youtube.diagnostics.runtime.registry import ACTION_REGISTRY


@dataclass(frozen=True)
class YouTubeActionTestRequest:
    device_id: str
    action_id: str
    params: dict


def validate_youtube_action_test_config(config: dict) -> YouTubeActionTestRequest | None:
    device_id = config.get("device_id", "")
    action_id = config.get("action_id", "")
    params = config.get("params", {})

    if not device_id:
        emit({"type": "result", "success": False, "message": "Missing device_id"})
        return None

    if not action_id:
        emit({"type": "result", "success": False, "message": "Missing action_id"})
        return None

    if action_id not in ACTION_REGISTRY:
        emit(
            {
                "type": "result",
                "success": False,
                "message": f"Unknown action: '{action_id}'. Available: {sorted(ACTION_REGISTRY.keys())}",
            }
        )
        return None

    return YouTubeActionTestRequest(device_id=device_id, action_id=action_id, params=params)


__all__ = [
    "YouTubeActionTestRequest",
    "validate_youtube_action_test_config",
]
