"""Shared UI wait helpers used by YouTube workflows and tests.

These factor out the duplicated `_wait_for_any` / `_try_tap` helpers from:
  - `taktik/core/social_media/youtube/workflows/publish/upload_workflow.py`
  - `bridges/youtube/diagnostics/action_test.py`

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

from taktik.core.shared.telemetry import emit_step


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
    started = time.time()
    deadline = started + timeout
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
    # Report the miss even when the caller passed no logger: a selector that stops matching is
    # how an app update announces itself, and it used to leave nothing but an optional log line.
    emit_step(
        "selector_miss",
        action="wait_for_any",
        target=(selectors[0][:120] if selectors else None),
        label=label or None,
        selector_count=len(selectors),
        timeout_s=timeout,
        elapsed_ms=round((time.time() - started) * 1000),
    )
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


def find_element(device, selectors: Sequence[str]):
    """First selector that matches RIGHT NOW, as an element. ``None`` if none match.

    No waiting: this answers "is it on screen already?". Use it when absence is a normal
    outcome — checking whether a popup is up, picking between two possible screens — where
    paying a timeout per selector would cost seconds on the common path.

    Returns the xpath handle (not a bool) so the caller can click or read it.
    """
    for selector in selectors or []:
        try:
            element = device.xpath(selector)
            if element.exists:
                return element
        except Exception:
            continue
    return None


def wait_for_element(device, selectors: Sequence[str], timeout: float = 5.0):
    """First selector that appears within ``timeout``, as an element. ``None`` otherwise.

    Use it when the element is EXPECTED and the screen may still be loading (a webview, an
    OTP mail, a freshly opened settings page).

    Beware the total cost: the deadline is applied PER SELECTOR, so a miss on a list of six
    costs ``6 * timeout``, not ``timeout``. That is the historical behaviour of every copy
    of this helper and it is kept deliberately — changing it here would silently retime
    every auth and signup flow. When a bounded TOTAL wait is what you want, use
    :func:`wait_for_any`, which scans all selectors inside one deadline.
    """
    started = time.time()
    for selector in selectors or []:
        try:
            element = device.xpath(selector)
            if element.wait(timeout=timeout):
                return element
        except Exception:
            continue
    emit_step(
        "selector_miss",
        action="wait_for_element",
        target=(selectors[0][:120] if selectors else None),
        selector_count=len(selectors or []),
        timeout_s=timeout,
        elapsed_ms=round((time.time() - started) * 1000),
    )
    return None


__all__ = ["wait_for_any", "try_tap", "find_element", "wait_for_element"]
