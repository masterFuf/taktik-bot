#!/usr/bin/env python3
"""Public Electron entrypoint for Instagram Smart Comment.

The implementation lives in `bridges.instagram.engagement.smart_comment`; this
file stays at the platform root because the Front dev resolver launches
`bridges/instagram/smart_comment_bridge.py` directly.
"""

from bridges.instagram.engagement.smart_comment import main


if __name__ == "__main__":
    main()
