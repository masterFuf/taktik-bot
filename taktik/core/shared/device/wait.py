"""Shared UI wait helpers used by YouTube workflows and tests.

These factor out the duplicated `_wait_for_any` / `_try_tap` helpers from:
  - `taktik/core/social_media/youtube/workflows/publish/upload_workflow.py`
  - `bridges/youtube/youtube_action_test_bridge.py`

Both implementations were byte-identical (deadline + scan loop). Centralizing
them avoids drift and makes it easier to reuse in future YouTube/Threads/Gmail
workflows without copy-pasting the same 20 lines.

Note: `taktik/core/shared/device/permissions.py` keeps its own private versions
because its `_try_tap` uses `xpath.wait()` per selector instead of the scan
loop — a subtly different total-time semantic. Migrating it would require
behavior verification, so we leave it alone for now.
"""

from __future__ import annotations

import time
from typing import Callable, Optional, Sequence


def wait_for_any(
    device,
    selectors: Sequence[str],
    timeout: float = 10.0,
    label: str = "",
    log: Optional[Callable[[str, str], None]] = None,
    poll_interval: float = 0.5,
) -> Optional[str]:
    """Return the first XPath selector that becomes visible within `timeout` seconds.

    Scans every selector in a tight deadline loop. Total wait time is bounded
    by `timeout` regardless of the number of selectors. If `log` is provided
    it is called with `(level, message)` for found / not-found events.

    Args:
        device: uiautomator2 device handle (must expose `.xpath(sel).exists`).
        selectors: XPath selectors to try.
        timeout: Maximum total wait in seconds.
        label: Optional tag prefixed in log messages.
        log: Optional `(level, msg)` callable (e.g. a wrapper around loguru).
        poll_interval: Seconds between scan rounds.

    Returns:
        The winning selector, or `None` if none matched within the deadline.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        for sel in selectors:
            try:
                if device.xpath(sel).exists:
                    if log:
                        log("debug", f"✅ [{label or 'found'}] selector: {sel}")
                    return sel
            except Exception:
                continue
        time.sleep(poll_interval)
    if log and label:
        log("debug", f"❌ [{label}] no match after {timeout:.0f}s ({len(selectors)} selectors tried)")
    return None


def try_tap(
    device,
    selectors: Sequence[str],
    timeout: float = 3.0,
    label: str = "",
    log: Optional[Callable[[str, str], None]] = None,
    poll_interval: float = 0.5,
) -> bool:
    """Find the first visible selector then tap it.

    Uses `wait_for_any` under the hood so total wait time is bounded by
    `timeout` instead of `timeout * len(selectors)`.

    Returns:
        True if a selector was found and tapped successfully, False otherwise.
    """
    found = wait_for_any(
        device,
        selectors,
        timeout=timeout,
        label=label,
        log=log,
        poll_interval=poll_interval,
    )
    if not found:
        return False
    try:
        device.xpath(found).click()
        return True
    except Exception as e:
        if log:
            log("warning", f"⚠️  [{label or 'tap'}] element found but click failed: {e}")
        return False


__all__ = ["wait_for_any", "try_tap"]
