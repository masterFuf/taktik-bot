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
    from bridges.instagram.analysis.runtime.persona_commands import run_persona_analysis_cli

    run_persona_analysis_cli(sys.argv[1:])


if __name__ == "__main__":
    main()


__all__ = ["PersonaAnalysisBridge", "main"]
