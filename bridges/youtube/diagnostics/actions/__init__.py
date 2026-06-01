"""YouTube diagnostic action families."""


def register_actions() -> None:
    """Import action families so decorators populate the registry."""
    from bridges.youtube.diagnostics.actions import detection  # noqa: F401
    from bridges.youtube.diagnostics.actions import keyboard  # noqa: F401
    from bridges.youtube.diagnostics.actions import navigation  # noqa: F401
    from bridges.youtube.diagnostics.actions import upload  # noqa: F401
    from bridges.youtube.diagnostics.actions import visibility  # noqa: F401


__all__ = ["register_actions"]
