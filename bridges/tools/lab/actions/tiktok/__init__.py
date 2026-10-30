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

    # The actions every platform registers, same id, one implementation.
    from bridges.tools.lab.actions.common.shared_actions import register_shared_actions
    register_shared_actions(action)


__all__ = ["ACTION_REGISTRY", "DETECTIONS", "action", "detection_action", "register_actions"]

