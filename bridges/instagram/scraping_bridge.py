#!/usr/bin/env python3
"""Public Electron entrypoint for Instagram scraping.

The implementation lives in `bridges.instagram.scraping.scraping`; this file
stays at the platform root because the Front dev resolver launches
`bridges/instagram/scraping_bridge.py` directly.
"""

from bridges.instagram.scraping.scraping import main


if __name__ == "__main__":
    main()
