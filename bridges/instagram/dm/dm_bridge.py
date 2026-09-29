#!/usr/bin/env python3
"""Instagram DM bridge entrypoint."""

import os
import sys


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, bot_dir)

from bridges.common.bootstrap import setup_environment

setup_environment()


def main():
    from bridges.common.entrypoint import NOT_AN_OBJECT, run_bridge_main
    from bridges.instagram.dm.commands import DMCommand, report_dm_entry_error

    run_bridge_main(DMCommand, usage="dm_bridge.py <config.json>", report_error=report_dm_entry_error,
                    messages={NOT_AN_OBJECT: "The DM config must be a JSON object"}, catch_crashes=False)


if __name__ == "__main__":
    main()


__all__ = ["main"]
