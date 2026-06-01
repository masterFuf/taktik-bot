#!/usr/bin/env python3
"""TikTok account bridge entrypoint."""

import os
import sys


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment

setup_environment()

from bridges.tiktok.account.runtime.account_commands import run_account_bridge_cli
from bridges.tiktok.account.runtime.bridge import TikTokAccountBridge


def main():
    sys.exit(run_account_bridge_cli(sys.argv[1:]))


if __name__ == "__main__":
    main()


__all__ = ["TikTokAccountBridge", "main"]
