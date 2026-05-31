#!/usr/bin/env python3
"""Public Electron entrypoint for Instagram DM.

The implementation lives in `bridges.instagram.engagement.dm`; this file stays
at the platform root because the Front dev resolver launches
`bridges/instagram/dm_bridge.py` directly.
"""

from bridges.instagram.engagement.dm import main


if __name__ == "__main__":
    main()
