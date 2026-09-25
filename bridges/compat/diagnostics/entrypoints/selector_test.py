#!/usr/bin/env python3
"""
Selector Test Bridge — tests the selectors production runs, on the screen of a real device.

Connects first, then takes production's steps on that phone (`runtime/selector_test/production.py`):
version overrides of the installed app (every version <= it), language detected on the screen,
catalogues read back with their properties. Each xpath is evaluated as `d.xpath()` evaluates it,
on one dump of the screen (`runtime/selector_test/runner.py`).

Config JSON (passed as argv[1] temp file):
  {
    "device_id": "CE7S00081E2148",
    "app": "instagram",
    "version": "417.0.0.54.77",
    "domains": ["navigation", "feed"]  // optional filter, empty = all
  }

Output: IPC messages with per-selector pass/fail results. `test_results` also carries
`baseline_version`, `overrides_applied`, `language`, `skipped_not_xpath` and `skipped_empty`.
"""

import sys
import os

# Bootstrap: ensure bot root is in sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.common.runtime.ipc import IPC
from bridges.common.device.connection import ConnectionService
from bridges.compat.diagnostics.runtime.selector_test.request import load_selector_test_request
from bridges.compat.diagnostics.runtime.selector_test.runner import (
    filter_selectors_by_domain,
    run_selector_tests,
    summarize_selector_results,
)
from loguru import logger


def main():
    ipc = IPC()

    request = load_selector_test_request(ipc, sys.argv)
    device_id = request.device_id
    app_name = request.app_name
    domain_filter = request.domain_filter

    logger.info(f"[SelectorTest] device={device_id} app={app_name} version={request.version} domains={domain_filter}")

    ipc.send("status", status="connecting", message=f"Connecting to {device_id}...")
    conn = ConnectionService(device_id)
    if not conn.connect():
        ipc.send("error", error=f"Failed to connect to {device_id}", error_code="CONNECTION_ERROR")
        sys.exit(1)

    try:
        _run(ipc, conn, request, app_name, device_id, domain_filter)
    finally:
        conn.disconnect()


def _run(ipc, conn, request, app_name, device_id, domain_filter):
    ipc.send("status", status="initializing", message="Resolving the selectors of the installed version...")
    try:
        from bridges.compat.diagnostics.runtime.selector_test.production import prepare_selector_test

        plan = prepare_selector_test(app_name, request.version, device_id, conn.device)
    except Exception as e:
        ipc.send("error", error=f"Failed to load selectors: {e}", error_code="REGISTRY_INIT_ERROR")
        sys.exit(1)

    selectors = plan.selectors
    version = selectors.version
    all_selectors = selectors.entries
    if not all_selectors:
        ipc.send("error", error=f"No selectors found for {app_name}", error_code="NO_SELECTORS")
        sys.exit(1)

    all_selectors = filter_selectors_by_domain(all_selectors, domain_filter)
    total = sum(len(entry.xpaths) for entry in all_selectors.values())

    ipc.send(
        "status",
        status="testing",
        message=(
            f"Testing {len(all_selectors)} selectors ({total} XPaths), "
            f"v{version or selectors.baseline_version}, language {selectors.language}..."
        ),
    )

    results = run_selector_tests(plan.device, all_selectors, ipc, xml=plan.xml, rewrite=plan.rewrite)
    passed, failed, domain_summary = summarize_selector_results(results)

    ipc.send(
        "test_results",
        app=app_name,
        version=version,
        device_id=device_id,
        total_actions=len(results),
        total_xpaths=total,
        passed=passed,
        failed=failed,
        domain_summary=domain_summary,
        results=results,
        baseline_version=selectors.baseline_version,
        overrides_applied=selectors.overrides_applied,
        language=selectors.language,
        skipped_not_xpath=selectors.skipped_not_xpath,
        skipped_empty=selectors.skipped_empty,
    )

    logger.info(f"[SelectorTest] Done: {passed}/{len(results)} actions have at least one matching XPath")

    status = "all_passed" if failed == 0 else "some_failed"
    ipc.send("status", status=status, message=f"{passed}/{len(results)} selectors matched on {app_name} v{version}")


if __name__ == "__main__":
    main()
