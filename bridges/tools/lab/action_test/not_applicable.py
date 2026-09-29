"""What the Lab reports when what a test needs is not there, said by the action itself.

The Lab auto-test counts a test "not applicable" only on this declaration (`details.not_applicable`,
read by the plan, `app/src/features/tools/cartography/data/autotestPlan.ts`): no follow request
pending, no popup to close, no carousel served, an ad on screen instead of a video. The plan never
guesses it. An action declares it only after it read the screen it expects and found the thing
absent; a screen it could not read, or another app in front, stays a failure (a "no" read on nothing
would hide a broken selector).

The action still did not do its work: `success` stays False, so the Lab's buttons do not show it as a
pass either.
"""

from typing import Callable, Optional

from bridges.tools.lab.action_test.detection_answer import app_screen_readable

#: The key of `details` the plan reads.
NOT_APPLICABLE = "not_applicable"


def not_applicable(action_id: str, reason: str, **details) -> dict:
    """The Lab result of an action whose target is absent: `reason` says what, on which screen."""
    return {
        "success": False,
        "message": f"{action_id}: not applicable, {reason}",
        "details": {**details, NOT_APPLICABLE: reason},
    }


def absent_on_screen(action_id: str, *, device, platform: str, still_there: Optional[Callable[[], bool]], what: str,
                     where: str = "on screen") -> dict:
    """The result of an action that found nothing to act on: not applicable when the screen, read and
    the app's, holds no `what`; a failure when it could not be read, or when the production detector
    (`still_there`) sees the thing the action did not act on."""
    if still_there is not None and still_there():
        return {"success": False, "message": f"{action_id}: {what} {where}, but the action did not act on it"}
    if not app_screen_readable(device, platform):
        return {"success": False, "message": f"{action_id}: screen unreadable or not {platform}'s, nothing concluded"}
    return not_applicable(action_id, f"no {what} {where}")


__all__ = ["NOT_APPLICABLE", "absent_on_screen", "not_applicable"]
