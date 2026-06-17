"""Garde anti-injection shell des deep links (username/URL scrapes interpoles dans device.shell)."""

from taktik.core.social_media.instagram.actions.atomic.navigation.deep_link_navigation import (
    _IG_USERNAME_RE,
    _SHELL_UNSAFE_RE,
)


def _valid_username(u: str) -> bool:
    return bool(_IG_USERNAME_RE.fullmatch(u))


def _safe_url(u: str) -> bool:
    return not _SHELL_UNSAFE_RE.search(u) and u.startswith('https://www.instagram.com/')


def test_valid_usernames_pass():
    for u in ['natgeo', 'marvin.ndiaye.extraits', 'a_b.c1', 'X' * 30]:
        assert _valid_username(u), u


def test_injection_usernames_rejected():
    for u in [
        'a"; rm -rf /',           # casse le guillemet + commande
        'a$(reboot)',             # substitution
        'a`id`',                  # backtick
        'a b',                    # espace
        'a;ls',                   # separateur
        'a&whoami',               # background/and
        'a|cat',                  # pipe
        'a' * 31,                 # trop long
        '',                       # vide
    ]:
        assert not _valid_username(u), u


def test_safe_post_url_passes():
    assert _safe_url('https://www.instagram.com/p/ABC123/')
    assert _safe_url('https://www.instagram.com/reel/XyZ_-9/')


def test_unsafe_post_url_rejected():
    assert not _safe_url('https://www.instagram.com/p/"; reboot/')
    assert not _safe_url('https://www.instagram.com/p/$(id)/')
    assert not _safe_url('https://evil.com/p/ABC/')          # mauvais host
    assert not _safe_url('https://www.instagram.com/p/a b/')  # espace
