#!/usr/bin/env python3
"""Instagram Smart Comment bridge entrypoint."""

import os
import sys


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment

setup_environment()

from bridges.instagram.engagement.runtime.smart_comment_bridge import SmartCommentBridge


def main():
    from bridges.instagram.engagement.runtime.smart_comment_commands import run_smart_comment_cli

    run_smart_comment_cli(sys.argv[1:])


if __name__ == "__main__":
    main()


__all__ = ["SmartCommentBridge", "main"]
