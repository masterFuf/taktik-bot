#!/usr/bin/env python3
"""Public Electron entrypoint for TikTok publish workflows.

The implementation lives in `bridges.tiktok.publish.publish`; this file stays
at the platform root because the Front dev resolver launches
`bridges/tiktok/tiktok_publish_bridge.py` directly.
"""

from bridges.tiktok.publish.publish import main


if __name__ == "__main__":
    main()
