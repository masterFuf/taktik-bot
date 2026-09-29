"""Blocking-modal recovery.

A mis-tap can open an UNEXPECTED sheet/dialog (the Direct share sheet sits right next to the
comment button) that silently BLOCKS a workflow: the bot keeps waiting for an element that will
never appear on the wrong screen. The WorkflowWatchdog is the time-based safety net (it recovers
after ~90s of no progress); this mixin is the cheap PROACTIVE counterpart the interaction engine
runs between action phases, so a stray modal is cleared immediately instead of stalling a profile.

Signatures live in `ui/selectors/support/blocking_modals.py` (single source of truth, shared with
the comment action and the watchdog).
"""

import time
from typing import Optional

from taktik.core.social_media.instagram.ui.selectors.support.blocking_modals import BLOCKING_MODAL_SELECTORS
from taktik.core.social_media.instagram.actions.base.ipc import IPCEmitter


class ModalRecoveryMixin:
    """Mixin: detect + back out of unexpected blocking modals (share sheet, stray sheets)."""

    def _detect_blocking_modal(self) -> Optional[str]:
        """Name of the blocking modal currently on screen, else None.

        Fast path: one combined xpath query across ALL signatures (single round-trip); only when
        that hits do we identify which signature matched (for logging / the Agent panel). Never
        raises — a detection failure must never crash a workflow."""
        try:
            combined = BLOCKING_MODAL_SELECTORS.combined_xpath()
            if not combined or not self.device.xpath(combined).exists:
                return None
            name = BLOCKING_MODAL_SELECTORS.identify(lambda q: bool(self.device.xpath(q).exists))
            return name or "unknown_blocking_modal"
        except Exception:
            return None

    def _recover_from_blocking_modal(self, username: str = "", context: str = "") -> Optional[str]:
        """If a known blocking modal is open, back out of it (up to 2 presses) and confirm it's gone.

        Returns the modal name that was recovered from (whether or not the back-out succeeded), or
        None when the screen was already clean. Emits an IPC event so the live copilot surfaces the
        recovery. Cheap in the common case: a single xpath query and an early return when nothing
        is open."""
        name = self._detect_blocking_modal()
        if not name:
            return None

        where = f" during {context}" if context else ""
        self.logger.warning(f"🧯 Blocking modal '{name}' detected{where} — backing out")

        for _ in range(2):
            try:
                self.device.press("back")
            except Exception:
                break
            time.sleep(0.6)
            if not self._detect_blocking_modal():
                break

        recovered = self._detect_blocking_modal() is None
        if recovered:
            self.logger.info(f"🧯 Recovered from blocking modal '{name}'")
        else:
            self.logger.error(f"🧯 Could NOT dismiss blocking modal '{name}' after 2 back presses")

        try:
            IPCEmitter.emit_action(
                'blocking_modal_recovered',
                username or "",
                {'modal': name, 'context': context, 'recovered': recovered},
            )
        except Exception:
            pass

        return name
