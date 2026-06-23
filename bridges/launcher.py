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
from pathlib import Path


BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))


# Bridge name → module path mapping
BRIDGE_MODULES = {
    # Instagram
    "desktop_bridge":       "bridges.instagram.automation.desktop",
    "dm_bridge":            "bridges.instagram.engagement.dm",
    "scraping_bridge":      "bridges.instagram.scraping.scraping",
    "cold_dm_bridge":       "bridges.instagram.engagement.cold_dm",
    "smart_comment_bridge": "bridges.instagram.engagement.smart_comment",
    "notifications_bridge": "bridges.instagram.engagement.notifications",
    "account_bridge":       "bridges.instagram.account.account",
    "taktik_agent_bridge":  "bridges.instagram.agent.taktik_agent",
    "persona_analysis_bridge": "bridges.instagram.analysis.persona",
    "publish_bridge":       "bridges.instagram.publish.publish",
    # TikTok
    "tiktok_bridge":          "bridges.tiktok.workflows.dispatcher",
    "tiktok_unfollow_bridge": "bridges.tiktok.automation.unfollow",
    "dm_outreach_bridge":     "bridges.tiktok.engagement.dm_outreach",
    "tiktok_scraping_bridge": "bridges.tiktok.scraping.scraping",
    "tiktok_account_bridge":  "bridges.tiktok.account.account",
    "tiktok_publish_bridge":  "bridges.tiktok.publish.publish",
    # Threads
    "threads_bridge": "bridges.threads.workflows.dispatcher",
    # Gmail
    "gmail_account_bridge": "bridges.gmail.account.account",
    # YouTube
    "youtube_account_bridge":     "bridges.youtube.account.account",
    "youtube_upload_bridge":      "bridges.youtube.publish.upload",
    "youtube_action_test_bridge": "bridges.youtube.diagnostics.action_test",
    # Compat
    "compat_bridge":            "bridges.compat.diagnostics.entrypoints.compat",
    "selector_test_bridge":     "bridges.compat.diagnostics.entrypoints.selector_test",
    "workflow_test_bridge":     "bridges.compat.diagnostics.entrypoints.workflow_test",
    "action_test_bridge":       "bridges.compat.diagnostics.entrypoints.action_test",
    "action_session_bridge":    "bridges.compat.diagnostics.entrypoints.action_session",
    "tiktok_action_test_bridge":"bridges.compat.diagnostics.entrypoints.tiktok_action_test",
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
