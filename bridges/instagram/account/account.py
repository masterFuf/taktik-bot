#!/usr/bin/env python3
"""Instagram account bridge entrypoint."""

import os
import sys


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment

setup_environment()

from bridges.instagram.account.runtime.bridge import AccountBridge
from bridges.common.runtime.entrypoint import run_bridge_main


def main():
    run_bridge_main(AccountBridge, usage="account_bridge.py <config_path>", catch_crashes=False)


if __name__ == "__main__":
    main()


__all__ = ["AccountBridge", "main"]
