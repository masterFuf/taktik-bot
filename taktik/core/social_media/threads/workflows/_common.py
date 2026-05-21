"""Shared helpers for Threads workflows.

Currently exposes `threads_startup()`, factored out from the byte-identical
60-line startup block that lived at the top of both `search_and_interact.py`
and `feed_and_interact.py`.

Pattern mirrors `tiktok_startup()` in `bridges/tiktok/base.py`.
"""

from __future__ import annotations

import random
import time
from typing import Callable, Optional, Sequence, Tuple

from taktik.core.social_media.threads import ThreadsManager
from taktik.core.social_media.threads import ui as tui


LogFn = Callable[[str, str], None]
StartupResult = Optional[Tuple[ThreadsManager, object, str]]


def _wait_any_resource(device, resource_ids: Sequence[str], timeout: float = 25.0, poll: float = 0.5):
    """Return (selector, rid) for the first matching resource-id, or (None, None)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for rid in resource_ids:
            sel = device(resourceId=rid)
            if sel.exists:
                return sel, rid
        time.sleep(poll)
    return None, None


def threads_startup(
    device_id: str,
    log: LogFn,
    anchors: Optional[Sequence[str]] = None,
) -> StartupResult:
    """Connect, restart Threads and wait for one of the expected anchor screens.

    Args:
        device_id: Android device serial.
        log: ``(level, message)`` callable. Used for all status reporting so
            callers can plug their own loguru wrapper / IPC forwarder.
        anchors: Resource-ids of the screens we accept as "Threads is ready".
            Defaults to the full main-feed / search / profile / SERP set.

    Returns:
        ``(manager, device, anchor_rid)`` when Threads is ready, or ``None``
        if any step fails (connect, install check, restart, anchor wait).
        Failures are reported through ``log("error", ...)`` and the diagnostic
        dump matches the previous inline behaviour.
    """
    if anchors is None:
        anchors = (
            tui.TABS_BOTTOM_BAR,
            tui.MAIN_FEED_SCREEN,
            tui.SEARCH_BAR,
            tui.PROFILE_SCREEN_ROOT,
            tui.SERP_MENU_BUTTON,
        )

    # ── Connect ─────────────────────────────────────────────────────────
    manager = ThreadsManager(device_id=device_id)
    if not manager.device_manager.connect():
        log("error", f"Failed to connect to device {device_id}")
        return None

    if not manager.is_installed():
        log("error", "Threads (com.instagram.barcelona) is not installed on this device")
        return None

    device = manager.device_manager.device

    # ── Restart for a clean state ───────────────────────────────────────
    log("info", "Restarting Threads for a clean initial state…")
    if not manager.restart():
        log("error", "Failed to restart Threads")
        return None

    # Cold start takes longer than a warm launch; give the UI time to settle.
    wait_after_launch = random.uniform(8.0, 12.0)
    log("info", f"Waiting {wait_after_launch:.1f}s for Threads to load…")
    time.sleep(wait_after_launch)

    # ── Anchor probe ────────────────────────────────────────────────────
    anchor, anchor_rid = _wait_any_resource(device, anchors, timeout=25.0)
    if anchor is None:
        _diagnose_missing_anchor(device, log)
        return None

    log("info", f"Threads UI ready (anchor={anchor_rid})")

    # If we somehow landed on a profile screen, back out to the main feed.
    if anchor_rid == tui.PROFILE_SCREEN_ROOT:
        for _ in range(3):
            device.press("back")
            time.sleep(0.6)
            if device(resourceId=tui.TABS_BOTTOM_BAR).exists:
                break

    # Wait for the main feed header (hamburger button) to be fully rendered.
    hamburger = device(resourceId=tui.MAIN_FEED_MENU_BUTTON)
    if not hamburger.wait(timeout=10.0):
        log("warning", "Main feed header not detected — proceeding anyway")
    else:
        log("info", "Main feed header ready")
        time.sleep(0.5)

    return manager, device, anchor_rid


def _diagnose_missing_anchor(device, log: LogFn) -> None:
    """Emit a diagnostic dump when no expected anchor appears."""
    try:
        current = device.app_current() or {}
        log(
            "error",
            "Threads UI did not appear after restart — "
            f"foreground package={current.get('package')!r} activity={current.get('activity')!r}",
        )
    except Exception as exc:  # noqa: BLE001
        log("error", f"Threads UI did not appear after restart (app_current failed: {exc})")

    # Sample visible resource-ids so we know what screen we are stuck on.
    try:
        visible_rids: list[str] = []
        for elem in device.xpath("//*[@resource-id]").all()[:40]:
            rid = elem.attrib.get("resource-id")
            if rid and rid not in visible_rids:
                visible_rids.append(rid)
        if visible_rids:
            log("info", f"Visible resource-ids on current screen: {visible_rids}")
    except Exception as exc:  # noqa: BLE001
        log("info", f"Could not enumerate visible resource-ids: {exc}")


__all__ = ["threads_startup"]
