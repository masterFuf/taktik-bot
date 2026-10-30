"""The Lab actions a screen of any platform has: one implementation, registered under the same id by
each platform, so that the bot's catalogue and the front's `actionCatalog` mirror each other."""

from bridges.tools.lab.actions.common.capture import capture_surface
from bridges.tools.lab.actions.common.screen_lock import lift_screen_lock


def register_shared_actions(action) -> None:
    """`action` is the platform's own decorator: each registry holds them under its own bundle."""
    action("app.capture_surface")(capture_surface)
    action("app.lift_screen_lock")(lift_screen_lock)


__all__ = ["register_shared_actions"]
