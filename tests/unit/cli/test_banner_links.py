"""The CLI banner sends people to the same Discord invite as the README.

The banner kept an expired invite while the README, the app's login screen and its licence
modal had moved to the current one: someone who started from the terminal landed on a dead link.
"""

from __future__ import annotations

import io
import re

from rich.console import Console

from taktik.cli.support import banner
from unit.paths import CORE

_INVITE = re.compile(r"discord\.(?:com/invite|gg)/([A-Za-z0-9]+)")


def _readme_invites() -> set[str]:
    return set(_INVITE.findall((CORE / "README.md").read_text(encoding="utf-8")))


def _banner_markup(monkeypatch) -> str:
    """The banner as written, markup included: the link target as well as the text shown."""

    class _NoUpdate:
        def __init__(self, _version):
            pass

        def check_for_updates(self):
            return False, None

    import taktik.cli.support.version_checker as version_checker

    monkeypatch.setattr(version_checker, "VersionChecker", _NoUpdate)
    monkeypatch.setattr(banner, "console", Console(file=io.StringIO(), width=200))
    shown = []
    real_fit = banner.Panel.fit

    def _fit(renderable, *args, **kwargs):
        shown.append(renderable)
        return real_fit(renderable, *args, **kwargs)

    monkeypatch.setattr(banner.Panel, "fit", _fit)
    banner.display_banner()
    assert len(shown) == 1
    return shown[0]


def test_the_readme_names_one_invite():
    assert len(_readme_invites()) == 1


def test_the_banner_gives_the_readme_invite(monkeypatch):
    banner_invites = _INVITE.findall(_banner_markup(monkeypatch))

    assert banner_invites, "the banner lost its Discord link"
    assert set(banner_invites) == _readme_invites()
