#!/usr/bin/env python3
"""Public Electron entrypoint for YouTube account workflows."""

import os
import sys

bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.youtube.account.account import main


if __name__ == "__main__":
    main()
