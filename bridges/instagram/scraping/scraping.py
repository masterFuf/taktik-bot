#!/usr/bin/env python3
"""Instagram scraping bridge entrypoint for TAKTIK Desktop."""

import os
import sys


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment

setup_environment()

from bridges.common.runtime.signal_handler import setup_signal_handlers
from bridges.common.runtime.entrypoint import MISSING_CONFIG, run_bridge_main
from bridges.instagram.scraping.runtime.runner import ScrapingRun, report_scraping_entry_error

setup_signal_handlers()


def main():
    run_bridge_main(ScrapingRun, usage="scraping_bridge <config.json>",
                    report_error=report_scraping_entry_error, messages={MISSING_CONFIG: "No config file provided"},
                    catch_crashes=False)


if __name__ == "__main__":
    main()
