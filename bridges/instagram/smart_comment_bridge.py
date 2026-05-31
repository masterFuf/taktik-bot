#!/usr/bin/env python3
"""Public Electron entrypoint for Instagram Smart Comment.

The implementation lives in `bridges.instagram.engagement.smart_comment`; this
file stays at the platform root because the Front dev resolver launches
`bridges/instagram/smart_comment_bridge.py` directly.
"""

import os
import sys

bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.instagram.engagement.smart_comment import main


if __name__ == "__main__":
    main()
