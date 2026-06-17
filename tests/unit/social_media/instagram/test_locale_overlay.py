"""Multi-language selector overlay (locales/) — Instagram profile pilot.

Locks the base + ``L()`` overlay behaviour:
- language-neutral resource-ids are ALWAYS present whatever the active locale;
- a known locale injects ONLY its own language fragments;
- the unknown locale falls back to the union of every language (= the legacy
  "keep-all" behaviour, so we never match fewer selectors than before);
- fields that historically had strings for one language only keep parity
  (no invented strings for the other language).

All assertions go through ``set_active_locale`` + the dataclass properties, which
is side-effect free (it never mutates the shared selector singletons), so tests
stay isolated. The destructive legacy in-place filter (``detect_and_optimize``
known-language path) is exercised by the Cartography Lab lot, not here.
"""
import pytest

from taktik.core.social_media.instagram.ui.selectors import PROFILE_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.locales import (
    set_active_locale,
    active_locale,
    available_locales,
)
from taktik.core.social_media.instagram.ui import language as ig_language


@pytest.fixture(autouse=True)
def _reset_locale():
    """Keep every test isolated: reset to the union (unknown) locale."""
    set_active_locale(None)
    yield
    set_active_locale(None)


# Language-neutral resource-ids that must survive in follow_button for any locale.
_NEUTRAL_FOLLOW_RIDS = (
    "profile_header_follow_button",
    ":id/follow_button",
)


def _joined(selectors):
    return "\n".join(selectors)


def test_available_locales():
    assert set(available_locales()) == {"en", "fr"}


def test_neutral_rids_present_in_every_locale():
    for loc in (None, "fr", "en"):
        set_active_locale(loc)
        joined = _joined(PROFILE_SELECTORS.follow_button)
        for rid in _NEUTRAL_FOLLOW_RIDS:
            assert rid in joined, f"missing {rid} for locale {loc!r}"


def test_fr_injects_only_french():
    set_active_locale("fr")
    follow = _joined(PROFILE_SELECTORS.follow_button)
    assert "Suivre" in follow
    assert "Follow" not in follow

    following = _joined(PROFILE_SELECTORS.following_button)
    assert "Abonné" in following and "Suivi(e)" in following
    assert "Following" not in following

    assert PROFILE_SELECTORS.private_text_contains == ["compte est privé"]
    assert PROFILE_SELECTORS.follow_button_text_labels == ["Suivre"]
    assert PROFILE_SELECTORS.message_button_text_labels == ["Message", "Envoyer un message"]


def test_en_injects_only_english():
    set_active_locale("en")
    follow = _joined(PROFILE_SELECTORS.follow_button)
    assert "Follow" in follow
    assert "Suivre" not in follow

    following = _joined(PROFILE_SELECTORS.following_button)
    assert "Following" in following
    assert "Abonné" not in following

    assert PROFILE_SELECTORS.private_text_contains == ["account is private"]
    assert PROFILE_SELECTORS.follow_button_text_labels == ["Follow"]
    # "Message" is identical in EN/FR -> stays in the neutral base.
    assert PROFILE_SELECTORS.message_button_text_labels == ["Message"]


def test_unknown_locale_is_union():
    set_active_locale(None)
    follow = _joined(PROFILE_SELECTORS.follow_button)
    assert "Suivre" in follow and "Follow" in follow
    assert set(PROFILE_SELECTORS.private_text_contains) == {
        "compte est privé",
        "account is private",
    }
    assert set(PROFILE_SELECTORS.follow_button_text_labels) == {"Suivre", "Follow"}


def test_zero_posts_parity_fr_only_strings():
    # Historically zero_posts only had FR content-desc strings. On EN we keep only
    # the neutral resource-id (no invented EN string) -> matches legacy behaviour.
    set_active_locale("en")
    assert PROFILE_SELECTORS.zero_posts_indicators == [
        '//*[@resource-id="com.instagram.android:id/profile_header_familiar_post_count_value" and @text="0"]',
    ]
    set_active_locale("fr")
    assert any("0publications" in s for s in PROFILE_SELECTORS.zero_posts_indicators)


def test_about_account_overlay():
    set_active_locale("fr")
    assert any("propos de ce compte" in s for s in PROFILE_SELECTORS.about_account_page_indicators)
    assert any("Compte basé" in s for s in PROFILE_SELECTORS.about_account_based_in_value)
    set_active_locale("en")
    assert any("About this account" in s for s in PROFILE_SELECTORS.about_account_page_indicators)
    assert any("Account based in" in s for s in PROFILE_SELECTORS.about_account_based_in_value)


def test_detect_and_optimize_unknown_override_is_safe_keep_all():
    # Unknown override returns early (no destructive in-place filtering) and
    # leaves the overlay in union mode.
    result = ig_language.detect_and_optimize(None, override="zz")
    assert result == "unknown"
    assert active_locale() is None
    follow = _joined(PROFILE_SELECTORS.follow_button)
    assert "Suivre" in follow and "Follow" in follow
