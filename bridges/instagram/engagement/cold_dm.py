#!/usr/bin/env python3
"""Instagram Cold DM bridge entrypoint (the workflow is the core's `run_instagram_cold_dm`)."""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from bridges.common.runtime.bootstrap import setup_environment

setup_environment(log_level="INFO")



def main():
    from bridges.common.runtime.entrypoint import CONFIG_ERROR, run_bridge_main
    from bridges.instagram.engagement.runtime.cold_dm.commands import ColdDmRun, report_cold_dm_entry_error

    run_bridge_main(ColdDmRun, usage="cold_dm_bridge.py <config_file>", report_error=report_cold_dm_entry_error,
                    messages={CONFIG_ERROR: "{error}"}, catch_crashes=False)


if __name__ == "__main__":
    main()


__all__ = ["main"]
