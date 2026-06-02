"""Instagram compat diagnostic action catalog."""

from bridges.compat.diagnostics.runtime.registry.actions import ActionRegistry


_registry = ActionRegistry()
ACTION_REGISTRY = _registry.actions
action = _registry.action


def register_actions() -> None:
    """Import action families so decorators populate the registry."""
    from bridges.compat.diagnostics.actions.instagram import comment  # noqa: F401
    from bridges.compat.diagnostics.actions.instagram import detection  # noqa: F401
    from bridges.compat.diagnostics.actions.instagram import keyboard  # noqa: F401
    from bridges.compat.diagnostics.actions.instagram import navigation  # noqa: F401
    from bridges.compat.diagnostics.actions.instagram import popups  # noqa: F401
    from bridges.compat.diagnostics.actions.instagram import post  # noqa: F401
    from bridges.compat.diagnostics.actions.instagram import profile  # noqa: F401
    from bridges.compat.diagnostics.actions.instagram import scroll  # noqa: F401
    from bridges.compat.diagnostics.actions.instagram import story  # noqa: F401


__all__ = ["ACTION_REGISTRY", "action", "register_actions"]

