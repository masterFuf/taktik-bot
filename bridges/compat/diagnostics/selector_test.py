#!/usr/bin/env python3
"""
Selector Test Bridge — Live-tests XPath selectors against a real device screen.

Connects to a device via uiautomator2, then tests each selector from the
VersionedSelectorRegistry by calling device.xpath(expr).exists on the live UI.

This validates that selectors still match real UI elements on any Instagram version.

Config JSON (passed as argv[1] temp file):
  {
    "device_id": "CE7S00081E2148",
    "app": "instagram",
    "version": "417.0.0.54.77",
    "domains": ["navigation", "feed"]  // optional filter, empty = all
  }

Output: IPC messages with per-selector pass/fail results.
"""

import sys
import os
import time

# Bootstrap: ensure bot root is in sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.common.runtime.ipc import IPC
from bridges.common.device.connection import ConnectionService
from bridges.compat.diagnostics.runtime.selector_request import load_selector_test_request
from bridges.compat.diagnostics.runtime.selector_runner import (
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
    version = request.version
    domain_filter = request.domain_filter

    logger.info(f"[SelectorTest] device={device_id} app={app_name} version={version} domains={domain_filter}")
    ipc.send("status", status="initializing", message="Loading selector registry...")

    # Initialize registry
    try:
        from taktik.core.compat.selectors import create_registry

        registry = create_registry()
    except Exception as e:
        ipc.send("error", error=f"Failed to create registry: {e}", error_code="REGISTRY_INIT_ERROR")
        sys.exit(1)

    # Get all selectors for this app/version
    all_selectors = registry.get_all(app_name, version)
    if not all_selectors:
        ipc.send("error", error=f"No selectors found for {app_name}", error_code="NO_SELECTORS")
        sys.exit(1)

    all_selectors = filter_selectors_by_domain(all_selectors, domain_filter)

    total = sum(len(entry.xpaths) for entry in all_selectors.values())
    ipc.send("status", status="connecting", message=f"Connecting to {device_id}...")

    # Connect to device
    conn = ConnectionService(device_id)
    if not conn.connect():
        ipc.send("error", error=f"Failed to connect to {device_id}", error_code="CONNECTION_ERROR")
        sys.exit(1)

    device = conn.device
    ipc.send("status", status="testing", message=f"Testing {len(all_selectors)} selectors ({total} XPaths)...")

    results = run_selector_tests(device, all_selectors, ipc)

    # Disconnect
    conn.disconnect()

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
    )

    logger.info(f"[SelectorTest] Done: {passed}/{len(results)} actions have at least one matching XPath")

    # Also send a final status
    status = "all_passed" if failed == 0 else "some_failed"
    ipc.send("status", status=status, message=f"{passed}/{len(results)} selectors matched on {app_name} v{version}")


if __name__ == "__main__":
    main()
