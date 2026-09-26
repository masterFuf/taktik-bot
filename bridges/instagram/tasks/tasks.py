#!/usr/bin/env python3
"""Instagram task bridge entrypoint.

Runs ONE task of the `instagram.task.*` family (a one-shot: no target list, no live panel)
and exits. The dispatch is the Agent registry itself — the same handlers the CLI and the
scheduler resolve — so a task exists exactly once and this bridge stays what a bridge is
meant to be: payload in, events out.
"""

import os
import sys


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment

setup_environment()

from bridges.instagram.tasks.runtime.bridge import TaskBridge
from bridges.common.runtime.entrypoint import run_bridge_main


def main():
    run_bridge_main(TaskBridge, usage="tasks.py <config_path>", catch_crashes=False)


if __name__ == "__main__":
    main()


__all__ = ["TaskBridge", "main"]
