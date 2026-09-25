#!/usr/bin/env python3
"""TikTok scraping bridge entrypoint: one JSON line on stdin, the run, the exit code.

SIGTERM and SIGINT stop the registered workflow and end the process with 0.
"""

from __future__ import annotations

from bridges.common.runtime.entrypoint import run_bridge_main
from bridges.tiktok.scraping.runtime.workflow import TikTokScrapingBridge


def main():
    """Main entry point - reads config from stdin."""
    run_bridge_main(
        TikTokScrapingBridge,
        usage="tiktok_scraping_bridge",
        install_signal_handlers=True,
        config_source="stdin",
    )


if __name__ == "__main__":
    main()
