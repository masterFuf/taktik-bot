#!/usr/bin/env python3
"""Public Electron entrypoint for Instagram automation sessions.

The implementation lives in `bridges.instagram.automation.desktop`; this file
stays at the platform root because the Front dev resolver launches
`bridges/instagram/desktop_bridge.py` directly.
"""

import os
import sys

bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.instagram.automation.desktop import main


if __name__ == "__main__":
    main()
