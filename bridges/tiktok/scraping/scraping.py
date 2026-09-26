#!/usr/bin/env python3
"""TikTok scraping bridge entrypoint: the config file, the run, the exit code.

SIGTERM and SIGINT stop the registered workflow and end the process with 0.
"""

from __future__ import annotations

from bridges.common.runtime.entrypoint import report_error_event, run_bridge_main
from bridges.tiktok.scraping.runtime.workflow import TikTokScrapingBridge


def main():
    """Main entry point - reads the config file."""
    run_bridge_main(
        TikTokScrapingBridge,
        usage="tiktok_scraping_bridge <config_path>",
        install_signal_handlers=True,
        report_error=report_error_event,
    )


if __name__ == "__main__":
    main()
