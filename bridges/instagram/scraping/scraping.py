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
from bridges.instagram.scraping.runtime.runner import run_scraping_bridge

setup_signal_handlers()


def main():
    sys.exit(run_scraping_bridge(sys.argv))


if __name__ == "__main__":
    main()
