#!/usr/bin/env python3
"""Instagram Persona Analysis bridge entrypoint."""

import os
import sys


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment

setup_environment()

from bridges.common.runtime.signal_handler import setup_signal_handlers
from bridges.instagram.analysis.runtime.persona_bridge import PersonaAnalysisBridge

setup_signal_handlers()


def main():
    from bridges.common.runtime.entrypoint import CONFIG_ERROR, run_bridge_main
    from bridges.instagram.analysis.runtime.persona_commands import PersonaAnalysisRun, report_persona_entry_error

    run_bridge_main(PersonaAnalysisRun, usage="persona_analysis_bridge.py <config.json>",
                    report_error=report_persona_entry_error, messages={CONFIG_ERROR: "Failed to read config: {error}"},
                    catch_crashes=False)


if __name__ == "__main__":
    main()


__all__ = ["PersonaAnalysisBridge", "main"]
