"""What the Lab reports for a detection: the answer, yes or no, on a screen it could read.

A detection asks the screen one question (is a post open, is the video liked...). "No" is a correct
answer as often as "yes": on the feed no post is open, most videos are not liked. Reported as a
failed action, a "no" turned the auto-test red on a correct answer. The production function is
called as the bot calls it; only the Lab's result changes: success, the answer in
``details.found``.

A "no" is an answer only when the screen was read and was the app's: one photo of the screen that
holds at least one widget of the app (official package, variant or clone). An empty dump, a dump
that does not parse, or another app in front is no answer, and the action fails; so does a
production function that answers None ("could not tell"). An exception is never caught here: the
runner reports it as a failure.
"""

from loguru import logger

from taktik.core.clone.packages.package_map import belongs_to_platform
from taktik.core.shared.device.snapshot import SnapshotUnavailable
from taktik.core.shared.device.ui_dump import iter_widgets


def app_screen_readable(device, platform: str) -> bool:
    """One photo of the screen holds a widget of ``platform``'s app."""
    try:
        photo = device.snapshot()
    except SnapshotUnavailable as exc:
        logger.warning(f"Detection: the screen could not be read ({exc})")
        return False
    return any(belongs_to_platform(widget.get("package"), platform) for widget in iter_widgets(photo.root))


def detection_answer(action_id: str, answer, *, device, platform: str) -> dict:
    """The Lab result of a detection whose production function answered ``answer``."""
    if answer is None:
        return {"success": False, "message": f"{action_id}: no answer (the detection could not tell)",
                "details": {"found": None}}
    if answer:
        return {"success": True, "message": f"{action_id}: yes", "details": {"found": True}}
    if not app_screen_readable(device, platform):
        return {"success": False,
                "message": f"{action_id}: screen unreadable or not {platform}'s, a no would mean nothing",
                "details": {"found": None}}
    return {"success": True, "message": f"{action_id}: no", "details": {"found": False}}


__all__ = ["app_screen_readable", "detection_answer"]
