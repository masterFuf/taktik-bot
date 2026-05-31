#!/usr/bin/env python3
"""Public Electron entrypoint for Instagram account workflows.

The implementation lives in `bridges.instagram.account.account`; this file
stays at the platform root because the Front dev resolver launches
`bridges/instagram/account_bridge.py` directly.
"""

from bridges.instagram.account.account import main


if __name__ == "__main__":
    main()
