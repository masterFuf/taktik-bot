"""The one look for a block after a gesture that writes, on every platform.

The detection belongs to each platform (Instagram: `ProblematicPageDetector.is_action_blocked`,
TikTok: `DetectionActions.is_action_blocked`); both read the screen, close nothing, and set the
run's stop latch (`run_halt.ACTION_BLOCKED`) when they see the platform refuse. This is the
wrapper every writing path calls after its gesture: copies of it had grown in four places, each
with its own guard, log and telemetry.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from taktik.core.shared.device.snapshot import SnapshotUnavailable
from taktik.core.shared.diagnostics import run_halt
from taktik.core.shared.telemetry.sink import emit_step


def look_for_action_block(detector: Any, *, after: str, target: str = '') -> bool:
    """After a write: must the run stop acting now? True on a block, or on any halt already set.

    One screen read, none when the latch is already set. Never raises. A screen the detector
    could not read (`SnapshotUnavailable`) proves nothing: the run is not stopped, and the log
    says the block could not be ruled out, instead of passing for a "no".
    """
    if run_halt.arret_demande():
        return True
    if detector is None or not hasattr(detector, 'is_action_blocked'):
        return False
    try:
        blocked = bool(detector.is_action_blocked())
    except SnapshotUnavailable as exc:
        logger.warning(f"Block check after {after}: screen unreadable ({exc}), a block cannot be "
                       "ruled out")
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Block check after {after} failed: {exc}")
        return False
    if blocked:
        # The detector's own code: a refusal of the gesture, or the platform checking the account.
        code = (run_halt.arret_demande() or {}).get('code') or run_halt.ACTION_BLOCKED
        logger.error(f"🛑 The platform refuses the {after}"
                     + (f" on @{target}" if target else "") + f" ({code}) — stopping the run")
        emit_step('account_restriction', action=code, target=target, after=after)
    return blocked


__all__ = ['look_for_action_block']
