#!/usr/bin/env python3
"""Instagram Cold DM bridge entrypoint."""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from bridges.common.runtime.bootstrap import setup_environment

setup_environment(log_level="INFO")

from bridges.instagram.engagement.runtime.cold_dm.workflow import ColdDMWorkflow


def main():
    from bridges.instagram.engagement.runtime.cold_dm.commands import run_cold_dm_cli

    run_cold_dm_cli(sys.argv[1:])


if __name__ == "__main__":
    main()


__all__ = ["ColdDMWorkflow", "main"]
