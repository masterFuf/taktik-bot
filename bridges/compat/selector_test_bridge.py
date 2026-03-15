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
import json
import time

# Bootstrap: ensure bot root is in sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.bootstrap import setup_environment
setup_environment()

from bridges.common.ipc import IPC
from bridges.common.connection import ConnectionService
from loguru import logger
from taktik.core.compat import create_registry


def main():
    ipc = IPC()

    # Parse config from temp file (argv[1])
    if len(sys.argv) < 2:
        ipc.send("error", error="No config file provided", error_code="MISSING_CONFIG")
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        ipc.send("error", error=f"Failed to read config: {e}", error_code="CONFIG_ERROR")
        sys.exit(1)

    device_id = config.get("device_id", "")
    app_name = config.get("app", "instagram")
    version = config.get("version", "")
    domain_filter = config.get("domains", [])  # empty = test all

    if not device_id:
        ipc.send("error", error="No device_id provided", error_code="MISSING_DEVICE")
        sys.exit(1)

    logger.info(f"[SelectorTest] device={device_id} app={app_name} version={version} domains={domain_filter}")
    ipc.send("status", status="initializing", message="Loading selector registry...")

    # Initialize registry
    try:
        registry = create_registry()
    except Exception as e:
        ipc.send("error", error=f"Failed to create registry: {e}", error_code="REGISTRY_INIT_ERROR")
        sys.exit(1)

    # Get all selectors for this app/version
    all_selectors = registry.get_all(app_name, version)
    if not all_selectors:
        ipc.send("error", error=f"No selectors found for {app_name}", error_code="NO_SELECTORS")
        sys.exit(1)

    # Filter by domains if specified
    if domain_filter:
        filtered = {}
        for action, entry in all_selectors.items():
            domain = action.split(".")[0]
            if domain in domain_filter:
                filtered[action] = entry
        all_selectors = filtered

    total = sum(len(entry.xpaths) for entry in all_selectors.values())
    ipc.send("status", status="connecting", message=f"Connecting to {device_id}...")

    # Connect to device
    conn = ConnectionService(device_id)
    if not conn.connect():
        ipc.send("error", error=f"Failed to connect to {device_id}", error_code="CONNECTION_ERROR")
        sys.exit(1)

    device = conn.device
    ipc.send("status", status="testing", message=f"Testing {len(all_selectors)} selectors ({total} XPaths)...")

    # Run tests
    results = []
    tested = 0

    for action, entry in sorted(all_selectors.items()):
        domain = action.split(".")[0]
        field_name = action.split(".", 1)[1] if "." in action else action

        xpath_results = []
        action_has_match = False

        for xpath in entry.xpaths:
            tested += 1
            found = False
            error_msg = None

            try:
                # Use uiautomator2's xpath engine — same as the bot at runtime
                found = device.xpath(xpath).exists
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"XPath error for {action}: {e}")

            if found:
                action_has_match = True

            xpath_results.append({
                "xpath": xpath,
                "found": found,
                "error": error_msg,
            })

        results.append({
            "action": action,
            "domain": domain,
            "field": field_name,
            "source": entry.source,
            "has_match": action_has_match,
            "xpaths": xpath_results,
        })

        # Send progress every 5 actions
        if len(results) % 5 == 0:
            ipc.send("progress", current=len(results), total=len(all_selectors), action=action)

    # Disconnect
    conn.disconnect()

    # Compute summary
    passed = sum(1 for r in results if r["has_match"])
    failed = sum(1 for r in results if not r["has_match"])

    # Group by domain
    domain_summary = {}
    for r in results:
        d = r["domain"]
        if d not in domain_summary:
            domain_summary[d] = {"total": 0, "passed": 0, "failed": 0}
        domain_summary[d]["total"] += 1
        if r["has_match"]:
            domain_summary[d]["passed"] += 1
        else:
            domain_summary[d]["failed"] += 1

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
