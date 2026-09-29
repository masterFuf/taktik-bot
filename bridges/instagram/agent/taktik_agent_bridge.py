#!/usr/bin/env python3
"""
Taktik Agent Bridge for TAKTIK Desktop.

Entry point launched by the Electron app for the autonomous Taktik Agent session.
Reads its JSON config file (`run_bridge_main`), connects to the Android device, and runs
the core Taktik Agent workflow.
"""

import os
import sys

# Bootstrap: UTF-8 + loguru + sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.bootstrap import setup_environment
setup_environment()

from bridges.common.signal_handler import setup_signal_handlers

from bridges.common.entrypoint import MISSING_CONFIG, report_error_event, run_bridge_main
from bridges.instagram.agent.commands import TaktikAgentRun

# Graceful shutdown on SIGINT / SIGTERM
setup_signal_handlers()


def main():
    run_bridge_main(TaktikAgentRun, usage="taktik_agent_bridge <config.json>",
                    report_error=report_error_event, messages={MISSING_CONFIG: "No config file provided"},
                    catch_crashes=False)


if __name__ == "__main__":
    main()
