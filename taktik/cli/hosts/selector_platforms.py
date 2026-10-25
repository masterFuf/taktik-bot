"""The platforms whose selectors the CLI registers with compat, when `taktik.cli.main` loads.

Both entry points (`taktik`, `taktik-tiktok`) and `python -m taktik` load that module before any
command, so before any phone connects. Each loader imports its platform at the first read only
(`compat/selectors/platforms.py`). The bridges register the same two at their entry
(`bridges/common/selector_platforms.py`): the CLI imports no bridge.
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
