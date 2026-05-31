#!/usr/bin/env python3
"""Public Electron entrypoint for Instagram automation sessions.

The implementation lives in `bridges.instagram.automation.desktop`; this file
stays at the platform root because the Front dev resolver launches
`bridges/instagram/desktop_bridge.py` directly.
"""

from bridges.instagram.automation.desktop import main


if __name__ == "__main__":
    main()
