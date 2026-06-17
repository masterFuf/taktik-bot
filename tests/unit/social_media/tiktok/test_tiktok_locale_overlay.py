"""Multi-language selector overlay (locales/) — TikTok sweep (lot 4).

Locks the base + ``L()`` overlay for TikTok: neutral resource-ids always present,
a known locale injects only its own language, unknown = union, and every selector
evaluates under each locale. Assertions go through ``set_active_locale`` (side-effect
free), so tests stay isolated.
"""
import pytest

from taktik.core.social_media.tiktok.ui.selectors import (
    NAVIGATION_SELECTORS,
    PROFILE_SELECTORS,
    INBOX_SELECTORS,
    AUTH_SELECTORS,
)
import taktik.core.social_media.tiktok.ui.selectors as TT_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.locales import (
    set_active_locale,
    active_locale,
    available_locales,
)
from taktik.core.social_media.tiktok.ui import language as tt_language


@pytest.fixture(autouse=True)
def _reset_locale():
    set_active_locale(None)
    yield
    set_active_locale(None)


def _joined(selectors):
    return "\n".join(selectors)


def test_available_locales():
    assert set(available_locales()) == {"en", "fr"}


def test_profile_follow_button_localized():
    set_active_locale("fr")
    assert any("Suivre" in s for s in PROFILE_SELECTORS.follow_button)
    set_active_locale("en")
    follow = _joined(PROFILE_SELECTORS.follow_button)
    assert "Follow" in follow
    assert "Suivre" not in follow


def test_inbox_accept_request_localized():
    set_active_locale("fr")
    assert any("Accepter" in s for s in INBOX_SELECTORS.accept_request_button)
    set_active_locale("en")
    assert any("Accept" in s for s in INBOX_SELECTORS.accept_request_button)


def test_auth_login_button_localized():
    set_active_locale("fr")
    assert any("Se connecter" in s for s in AUTH_SELECTORS.login_button)
    set_active_locale("en")
    assert any("Log in" in s for s in AUTH_SELECTORS.login_button)


def test_unknown_locale_is_union():
    set_active_locale(None)
    follow = _joined(PROFILE_SELECTORS.follow_button)
    assert "Suivre" in follow and "Follow" in follow


def test_override_unknown_is_safe():
    assert tt_language.detect_and_optimize(None, override="zz") == "unknown"
    assert active_locale() is None


def test_all_tiktok_selectors_evaluate_under_every_locale():
    for loc in (None, "fr", "en"):
        set_active_locale(loc)
        for name in dir(TT_SELECTORS):
            if not name.endswith("_SELECTORS"):
                continue
            inst = getattr(TT_SELECTORS, name)
            for attr in dir(inst):
                if attr.startswith("_"):
                    continue
                getattr(inst, attr)  # must not raise
