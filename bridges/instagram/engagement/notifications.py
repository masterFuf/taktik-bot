#!/usr/bin/env python3
"""Instagram notifications engagement bridge entrypoint."""

import os
import sys


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment

setup_environment()

from bridges.instagram.engagement.runtime.notifications.bridge import NotificationsBridge


def main():
    from bridges.common.runtime.entrypoint import NOT_AN_OBJECT, run_bridge_main
    from bridges.instagram.engagement.runtime.notifications.commands import (
        NotificationsCommand,
        report_notifications_entry_error,
    )

    run_bridge_main(NotificationsCommand, usage="notifications_bridge <config.json>",
                    report_error=report_notifications_entry_error,
                    messages={NOT_AN_OBJECT: "The notifications config must be a JSON object"}, catch_crashes=False)


if __name__ == "__main__":
    main()


__all__ = ["NotificationsBridge", "main"]
