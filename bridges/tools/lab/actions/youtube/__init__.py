"""YouTube diagnostic action families."""


def register_actions() -> None:
    """Import action families so decorators populate the registry."""
    from bridges.tools.lab.actions.youtube import detection  # noqa: F401
    from bridges.tools.lab.actions.youtube import keyboard  # noqa: F401
    from bridges.tools.lab.actions.youtube import navigation  # noqa: F401
    from bridges.tools.lab.actions.youtube import upload  # noqa: F401
    from bridges.tools.lab.actions.youtube import visibility  # noqa: F401


__all__ = ["register_actions"]
