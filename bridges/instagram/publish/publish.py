#!/usr/bin/env python3
"""Instagram publish bridge entrypoint."""

import os
import sys


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment

setup_environment()

from bridges.instagram.publish.runtime.bridge import InstagramPublishBridge
from bridges.instagram.publish.runtime.commands import run_publish_bridge_cli


def main():
    sys.exit(run_publish_bridge_cli(sys.argv[1:]))


if __name__ == "__main__":
    main()


__all__ = ["InstagramPublishBridge", "main"]
