"""U8: the unfollow reads its list through the locale layer, in English as in French.

The list path used to look for the literal "Following" and "Unfollow": on a phone in French no
button was ever found. Rows are now read through the shared state classifier.
"""

import logging

import pytest

from fake_follow_list import FakeFacade, FakeScreen, PKG, follow_list_xml
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.mixins.actions import (
    UnfollowActionsMixin,
)
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.mixins.sync_following import (
    SyncFollowingMixin,
)
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale


class _Probe(SyncFollowingMixin, UnfollowActionsMixin):
    def __init__(self, screen):
        self.device = FakeFacade(screen)
        self.logger = logging.getLogger("test-unfollow")


@pytest.fixture(autouse=True)
def _reset_locale():
    yield
    set_active_locale(None)


def _states(rows):
    return [(row["username"], row["state"]) for row in rows]


def test_french_447_rows_are_read_as_following_and_follow_back():
    set_active_locale("fr")
    screen = FakeScreen(follow_list_xml([("alice.fr", "Suivi(e)"), ("bob_fr", "Suivre en retour"),
                                         ("claire", "Suivre")]))
    assert _states(_Probe(screen)._visible_follow_rows()) == [
        ("alice.fr", "following"), ("bob_fr", "follow_back"), ("claire", "follow")]


def test_english_rows_are_read_with_the_same_classifier():
    set_active_locale("en")
    screen = FakeScreen(follow_list_xml([("alice", "Following"), ("bob", "Follow back"),
                                         ("carol", "Requested")]))
    assert _states(_Probe(screen)._visible_follow_rows()) == [
        ("alice", "following"), ("bob", "follow_back"), ("carol", "requested")]


def test_an_anonymous_row_is_never_offered_for_an_unfollow():
    """A button with no username at its height used to be tapped and recorded on 'unknown'."""
    set_active_locale("fr")
    screen = FakeScreen(follow_list_xml([(None, "Suivi(e)"), ("dave", "Suivi(e)")]))
    probe = _Probe(screen)
    assert _states(probe._visible_follow_rows()) == [("dave", "following")]
    assert [row["state"] for row in probe._visible_follow_rows(require_username=False)] == [
        "following", "following"]


def test_the_follow_back_view_is_recognised_in_french():
    set_active_locale("fr")
    assert _Probe(FakeScreen(follow_list_xml([("eve", "Suivre en retour")])))._has_follow_back_row()
    assert not _Probe(FakeScreen(follow_list_xml([("eve", "Suivi(e)")])))._has_follow_back_row()


def _dialog(label):
    return (f'<node index="9" text="{label}" resource-id="{PKG}:id/primary_button" '
            f'class="android.widget.Button" content-desc="" bounds="[100,1800][980,1900]" />')


@pytest.mark.parametrize("lang,label", [("fr", "Ne plus suivre"), ("en", "Unfollow")])
def test_the_private_account_confirmation_is_found_in_each_language(lang, label):
    set_active_locale(lang)
    screen = FakeScreen(follow_list_xml([("frank", "Suivi(e)")], extra=_dialog(label)))
    probe = _Probe(screen)
    assert probe._tap_unfollow_confirm(timeout=0) is True
    assert probe.device.taps == [(100, 1800, 980, 1900)]


def test_no_confirmation_dialog_means_no_tap():
    set_active_locale("fr")
    probe = _Probe(FakeScreen(follow_list_xml([("frank", "Suivi(e)")])))
    assert probe._tap_unfollow_confirm(timeout=0) is False
    assert probe.device.taps == []
