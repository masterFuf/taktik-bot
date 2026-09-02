"""The live callbacks of a profile-visiting TikTok workflow, wired in ONE place.

Followers, Target Profiles and Post URL all walk profiles the same way and all report the same
four things: an action, a visited profile, the running stats, a pause. Two bridges wired those
four by hand, in two near-identical copies that differed only in how they shaped the stats
payload -- and that is exactly how one of them ended up without the profile callback.

The cost was silent and measured on a real run: Target Profiles captured @yam_7770's avatar
(256x256, 14 Ko, logged as captured), handed it to `_send_profile`, which returns immediately when
nothing is listening. The picture was paid for on the device and thrown away, and the profile card
kept showing a letter in a coloured circle. The AI classification, wired separately, arrived fine
-- so the run looked like it had worked.

Only the stats sender ever differed between the two bridges, so it is the only parameter. Adding a
callback to the family now reaches every bridge at once, which is the whole point:
`scripts/audit_workflow_callbacks.py` fails if a bridge wires one by hand again.
"""

from __future__ import annotations

from typing import Any, Callable

from bridges.tiktok.runtime.ipc import logger, send_action, send_pause, send_profile_captured


def wire_workflow_callbacks(workflow: Any, *, on_stats: Callable[[dict], None]) -> None:
    """Wire every live callback of a profile-visiting workflow.

    `on_stats` is the caller's own: a single-target run reports its totals differently from a run
    distributing a budget across targets, and that difference is the only real one.
    """

    def on_action(action_info):
        send_action(action_info.get("action", "unknown"), action_info.get("target", ""))
        logger.info(f"🎯 Action: {action_info.get('action')} on @{action_info.get('target', '')}")

    def on_profile(profile_data):
        send_profile_captured(profile_data)

    def on_pause(duration: int):
        send_pause(duration)
        logger.info(f"⏸️ Taking a break for {duration}s")

    workflow.set_on_action_callback(on_action)
    workflow.set_on_profile_callback(on_profile)
    workflow.set_on_stats_callback(on_stats)
    workflow.set_on_pause_callback(on_pause)


__all__ = ["wire_workflow_callbacks"]
