"""
TAKTIK Bridge Launcher
======================
Single executable that routes to the appropriate bridge based on the first
command-line argument.

Instead of shipping 22 separate ~52 MB PyInstaller executables (total ~1.1 GB),
we compile ONE launcher that includes all bridge modules.

Usage:
    taktik_launcher.exe <bridge_name> [bridge_args...]

Example:
    taktik_launcher.exe desktop_bridge
    taktik_launcher.exe tiktok_bridge
"""

import sys
import json


# Bridge name → module path mapping
BRIDGE_MODULES = {
    # Instagram
    "desktop_bridge":       "bridges.instagram.desktop_bridge",
    "dm_bridge":            "bridges.instagram.dm_bridge",
    "scraping_bridge":      "bridges.instagram.scraping_bridge",
    "cold_dm_bridge":       "bridges.instagram.cold_dm_bridge",
    "discovery_bridge":     "bridges.instagram.discovery_bridge",
    "smart_comment_bridge": "bridges.instagram.smart_comment_bridge",
    "account_bridge":       "bridges.instagram.account_bridge",
    "taktik_agent_bridge":  "bridges.instagram.taktik_agent_bridge",
    # TikTok
    "tiktok_bridge":          "bridges.tiktok.tiktok_bridge",
    "tiktok_unfollow_bridge": "bridges.tiktok.tiktok_unfollow_bridge",
    "dm_outreach_bridge":     "bridges.tiktok.dm_outreach_bridge",
    "tiktok_scraping_bridge": "bridges.tiktok.scraping_bridge",
    "tiktok_account_bridge":  "bridges.tiktok.tiktok_account_bridge",
    "tiktok_publish_bridge":  "bridges.tiktok.tiktok_publish_bridge",
    # Threads
    "threads_bridge": "bridges.threads.threads_bridge",
    # Gmail
    "gmail_account_bridge": "bridges.gmail.gmail_account_bridge",
    # YouTube
    "youtube_account_bridge":     "bridges.youtube.youtube_account_bridge",
    "youtube_upload_bridge":      "bridges.youtube.youtube_upload_bridge",
    "youtube_action_test_bridge": "bridges.youtube.youtube_action_test_bridge",
    # Compat
    "compat_bridge":            "bridges.compat.compat_bridge",
    "selector_test_bridge":     "bridges.compat.selector_test_bridge",
    "workflow_test_bridge":     "bridges.compat.workflow_test_bridge",
    "action_test_bridge":       "bridges.compat.action_test_bridge",
    "tiktok_action_test_bridge":"bridges.compat.tiktok_action_test_bridge",
}


def main():
    if len(sys.argv) < 2:
        error = {"type": "error", "message": "Usage: taktik_launcher.exe <bridge_name> [args...]"}
        print(json.dumps(error), flush=True)
        sys.exit(1)

    bridge_name = sys.argv[1]

    if bridge_name not in BRIDGE_MODULES:
        error = {"type": "error", "message": f"Unknown bridge: '{bridge_name}'. Available: {list(BRIDGE_MODULES.keys())}"}
        print(json.dumps(error), flush=True)
        sys.exit(1)

    # Shift argv so the bridge sees itself as the "script":
    # Before: ["taktik_launcher.exe", "desktop_bridge", ...]
    # After:  ["desktop_bridge", ...]
    sys.argv = sys.argv[1:]

    # Lazy import — only loads the requested bridge and its deps
    import importlib
    module = importlib.import_module(BRIDGE_MODULES[bridge_name])
    module.main()


if __name__ == "__main__":
    main()
