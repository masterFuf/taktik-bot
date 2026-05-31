#!/usr/bin/env python3
"""Public Electron entrypoint for compatibility registry diagnostics."""

import os
import sys

bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.compat.diagnostics.compat import main


if __name__ == "__main__":
    main()
