"""The platforms whose selectors the bridges register with compat, at the entry of every bridge.

`run_bridge_main` calls `register_selector_platforms` before it builds the bridge, so before any
phone connects; a script or the test harness that drives the bot calls it too. Each loader
imports its platform at the first read only (`compat/selectors/platforms.py`).
"""

from taktik.core.compat.selectors.platforms import PlatformSelectors, register_platform


def _instagram() -> PlatformSelectors:
    from taktik.core.social_media.instagram.ui.selectors.domains import CATALOGUES

    return CATALOGUES


def _tiktok() -> PlatformSelectors:
    from taktik.core.social_media.tiktok.ui.selectors.domains import CATALOGUES

    return CATALOGUES


def register_selector_platforms() -> None:
    register_platform("instagram", _instagram)
    register_platform("tiktok", _tiktok)
