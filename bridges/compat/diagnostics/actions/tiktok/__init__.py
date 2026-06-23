"""TikTok compat diagnostic action catalog."""

from bridges.compat.diagnostics.runtime.registry.actions import ActionRegistry


_registry = ActionRegistry()
ACTION_REGISTRY = _registry.actions
action = _registry.action


def register_actions() -> None:
    """Import action families so decorators populate the registry."""
    from bridges.compat.diagnostics.actions.tiktok import account  # noqa: F401
    from bridges.compat.diagnostics.actions.tiktok import app  # noqa: F401
    from bridges.compat.diagnostics.actions.tiktok import detection  # noqa: F401
    from bridges.compat.diagnostics.actions.tiktok import inbox  # noqa: F401
    from bridges.compat.diagnostics.actions.tiktok import navigation  # noqa: F401
    from bridges.compat.diagnostics.actions.tiktok import popups  # noqa: F401
    from bridges.compat.diagnostics.actions.tiktok import publish  # noqa: F401
    from bridges.compat.diagnostics.actions.tiktok import scroll  # noqa: F401
    from bridges.compat.diagnostics.actions.tiktok import search  # noqa: F401
    from bridges.compat.diagnostics.actions.tiktok import video  # noqa: F401


__all__ = ["ACTION_REGISTRY", "action", "register_actions"]

