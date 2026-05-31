#!/usr/bin/env python3
"""Public Electron entrypoint for TikTok account workflows.

The implementation lives in `bridges.tiktok.account.account`; this file stays
at the platform root because the Front dev resolver launches
`bridges/tiktok/tiktok_account_bridge.py` directly.
"""

import os
import sys

bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.tiktok.account.account import main


if __name__ == "__main__":
    main()
