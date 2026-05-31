#!/usr/bin/env python3
"""Public Electron entrypoint for the Instagram Taktik Agent bridge.

The implementation lives in `bridges.instagram.agent.taktik_agent`; this file
stays at the platform root because the Front dev resolver launches
`bridges/instagram/taktik_agent_bridge.py` directly.
"""

from bridges.instagram.agent.taktik_agent import main


if __name__ == "__main__":
    main()
