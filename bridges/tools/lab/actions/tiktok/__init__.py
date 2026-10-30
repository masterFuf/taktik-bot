"""The TikTok actions of the Lab."""

from bridges.tools.lab.registry.actions import ActionRegistry


_registry = ActionRegistry(platform="tiktok")
ACTION_REGISTRY = _registry.actions
action = _registry.action
#: A yes/no question of the screen: the Lab reports its answer, yes or no (`detection_answer`).
detection_action = _registry.detection
DETECTIONS = _registry.detections


def register_actions() -> None:
    """Import action families so decorators populate the registry."""
    from bridges.tools.lab.actions.tiktok import account  # noqa: F401
    from bridges.tools.lab.actions.tiktok import app  # noqa: F401
    from bridges.tools.lab.actions.tiktok import comments  # noqa: F401
    from bridges.tools.lab.actions.tiktok import detection  # noqa: F401
    from bridges.tools.lab.actions.tiktok import followers  # noqa: F401
    from bridges.tools.lab.actions.tiktok import inbox  # noqa: F401
    from bridges.tools.lab.actions.tiktok import navigation  # noqa: F401
    from bridges.tools.lab.actions.tiktok import popups  # noqa: F401
    from bridges.tools.lab.actions.tiktok import profile  # noqa: F401
    from bridges.tools.lab.actions.tiktok import publish  # noqa: F401
    from bridges.tools.lab.actions.tiktok import scroll  # noqa: F401
    from bridges.tools.lab.actions.tiktok import search  # noqa: F401
    from bridges.tools.lab.actions.tiktok import settings  # noqa: F401
    from bridges.tools.lab.actions.tiktok import unfollow  # noqa: F401
    from bridges.tools.lab.actions.tiktok import video  # noqa: F401

    # Shared by every platform, same id, one implementation: the id stays a literal for the source scan.
    from bridges.tools.lab.actions.common.capture import capture_surface as _capture
    from bridges.tools.lab.actions.common.screen_lock import lift_screen_lock as _lift_screen_lock
    action("app.capture_surface")(_capture)
    action("app.lift_screen_lock")(_lift_screen_lock)


__all__ = ["ACTION_REGISTRY", "DETECTIONS", "action", "detection_action", "register_actions"]

