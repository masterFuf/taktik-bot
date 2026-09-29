"""Live selector execution helpers for compat selector diagnostics.

Each selector is evaluated the way `d.xpath(selector).exists` evaluates it: uiautomator2's own
`XPathSelector` on the tree `parse_ui_dump` also builds (tags = widget classes), shorthands
(`@id`, `%text%`, `^regex`) and `re:` included, after the device's rewrite when it has one
(`CloneAwareDeviceProxy.rewrite_xpath` on Instagram). `ScreenSnapshot` is that path.
"""

import time
from typing import Callable, Optional

from loguru import logger

from taktik.core.shared.device.snapshot import ScreenSnapshot, SnapshotUnavailable


def filter_selectors_by_domain(all_selectors: dict, domain_filter: list) -> dict:
    """Return selectors matching requested domains, or all selectors if no filter is set."""
    if not domain_filter:
        return all_selectors

    filtered = {}
    for action, entry in all_selectors.items():
        domain = action.split(".")[0]
        if domain in domain_filter:
            filtered[action] = entry
    return filtered


def take_screen(device) -> tuple[Optional[str], Optional[str]]:
    """The dump `d.xpath()` would take: (xml, None), or (None, error)."""
    try:
        return device.dump_hierarchy(), None
    except Exception as exc:
        return None, str(exc)


def run_selector_tests(
    device,
    all_selectors: dict,
    ipc,
    *,
    xml: Optional[str] = None,
    rewrite: Optional[Callable[[str], str]] = None,
) -> list[dict]:
    """Test every selector on one dump of the screen (`xml`, taken here when absent).

    `device` is what production calls `xpath()` on; it answers only when no dump could be read.
    """
    results = []
    snapshot, snapshot_error = _build_snapshot(device, xml, rewrite)
    mode = "xml_snapshot" if snapshot is not None else "live_device"

    if snapshot_error:
        logger.warning(f"Selector snapshot unavailable, falling back to live XPath calls: {snapshot_error}")
    else:
        logger.info("Selector test runner using one XML snapshot for local XPath evaluation")

    for action, entry in sorted(all_selectors.items()):
        domain = action.split(".")[0]
        field_name = action.split(".", 1)[1] if "." in action else action

        xpath_results = []
        action_has_match = False

        for xpath in entry.xpaths:
            started_at = time.perf_counter()
            if snapshot is not None:
                found, error_msg = _run_snapshot_xpath(snapshot, xpath, action)
            else:
                found, error_msg = _run_live_xpath(device, xpath, action)
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)

            if found:
                action_has_match = True

            xpath_results.append(
                {
                    "xpath": xpath,
                    "found": found,
                    "error": error_msg,
                    "elapsed_ms": elapsed_ms,
                    "mode": mode,
                }
            )

        results.append(
            {
                "action": action,
                "domain": domain,
                "field": field_name,
                "source": entry.source,
                "has_match": action_has_match,
                "xpaths": xpath_results,
            }
        )

        if len(results) % 5 == 0:
            ipc.send("progress", current=len(results), total=len(all_selectors), action=action)

    return results


def _build_snapshot(device, xml: Optional[str], rewrite) -> tuple[Optional[ScreenSnapshot], Optional[str]]:
    if xml is None:
        xml, error = take_screen(device)
        if xml is None:
            return None, error
    try:
        return ScreenSnapshot(xml, rewrite=rewrite), None
    except SnapshotUnavailable as exc:
        return None, str(exc)


def _run_snapshot_xpath(snapshot: ScreenSnapshot, xpath: str, action: str) -> tuple[bool, Optional[str]]:
    # An xpath uiautomator2 rejects on the photo is rejected by `d.xpath()` too: no live retry.
    try:
        return bool(snapshot.elements(xpath)), None
    except Exception as exc:
        logger.warning(f"XPath error for {action}: {exc}")
        return False, str(exc)


def _run_live_xpath(device, xpath: str, action: str) -> tuple[bool, Optional[str]]:
    try:
        return bool(device.xpath(xpath).exists), None
    except Exception as exc:
        logger.warning(f"XPath error for {action}: {exc}")
        return False, str(exc)


def summarize_selector_results(results: list[dict]) -> tuple[int, int, dict]:
    """Return passed/failed counts and per-domain summary."""
    passed = sum(1 for result in results if result["has_match"])
    failed = sum(1 for result in results if not result["has_match"])

    domain_summary = {}
    for result in results:
        domain = result["domain"]
        if domain not in domain_summary:
            domain_summary[domain] = {"total": 0, "passed": 0, "failed": 0}
        domain_summary[domain]["total"] += 1
        if result["has_match"]:
            domain_summary[domain]["passed"] += 1
        else:
            domain_summary[domain]["failed"] += 1

    return passed, failed, domain_summary


__all__ = ["filter_selectors_by_domain", "run_selector_tests", "summarize_selector_results", "take_screen"]
