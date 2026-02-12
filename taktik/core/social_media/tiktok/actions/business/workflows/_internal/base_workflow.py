"""Base TikTok Workflow — shared lifecycle, atomic actions, and stats callback.

Provides:
    - Atomic action helpers (click, navigation, scroll, detection)
    - Shared popup handler
    - Lifecycle: stop / pause / resume / _wait_if_paused
    - _send_stats_update (requires self.stats with .to_dict())
    - _on_stats_callback setter

Subclasses add their own callbacks, config, stats dataclass, and run().
"""

import time
from typing import Optional, Callable, Dict, Any
from loguru import logger

from ....atomic.click_actions import ClickActions
from ....atomic.navigation_actions import NavigationActions
from ....atomic.scroll_actions import ScrollActions
from ....atomic.detection_actions import DetectionActions
from .popup_handler import PopupHandler


class BaseTikTokWorkflow:
    """Lightweight base for TikTok workflows that share atomic actions and lifecycle."""

    def __init__(self, device, *, module_name: str = "tiktok-workflow"):
        self.device = device

        # Atomic actions
        self.click = ClickActions(device)
        self.navigation = NavigationActions(device)
        self.scroll = ScrollActions(device)
        self.detection = DetectionActions(device)

        # Shared popup handler
        self._popup_handler = PopupHandler(self.click, self.detection)

        self.logger = logger.bind(module=module_name)

        # Lifecycle state
        self._running = False
        self._paused = False

        # Stats callback
        self._on_stats_callback: Optional[Callable] = None

    # ------------------------------------------------------------------
    # Stats callback
    # ------------------------------------------------------------------

    def set_on_stats_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback called after each action to send real-time stats."""
        self._on_stats_callback = callback

    def _send_stats_update(self):
        """Send current stats via callback. Requires self.stats.to_dict()."""
        if self._on_stats_callback:
            try:
                self._on_stats_callback(self.stats.to_dict())
            except Exception as e:
                self.logger.warning(f"Error sending stats: {e}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop(self):
        """Stop the workflow."""
        self._running = False
        self.logger.info("🛑 Workflow stop requested")

    def pause(self):
        """Pause the workflow."""
        self._paused = True
        self.logger.info("⏸️ Workflow paused")

    def resume(self):
        """Resume the workflow."""
        self._paused = False
        self.logger.info("▶️ Workflow resumed")

    def _wait_if_paused(self):
        """Block while paused, return False if stopped during pause."""
        while self._paused and self._running:
            time.sleep(1)
        return self._running

    # ------------------------------------------------------------------
    # Popup handling
    # ------------------------------------------------------------------

    def _handle_popups(self):
        """Check for and close any popups that might block interaction."""
        return self._popup_handler.close_all()
