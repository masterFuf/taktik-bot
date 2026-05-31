#!/usr/bin/env python3
"""Public Electron entrypoint for Instagram persona analysis.

The implementation lives in `bridges.instagram.analysis.persona`; this file
stays at the platform root because the Front dev resolver launches
`bridges/instagram/persona_analysis_bridge.py` directly.
"""

from bridges.instagram.analysis.persona import main


if __name__ == "__main__":
    main()
