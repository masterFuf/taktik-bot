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
    from bridges.instagram.engagement.runtime.notifications.commands import run_notifications_cli

    run_notifications_cli(sys.argv[1:])


if __name__ == "__main__":
    main()


__all__ = ["NotificationsBridge", "main"]
