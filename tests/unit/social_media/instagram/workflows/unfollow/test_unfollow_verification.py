"""U3: an unfollow counts only when the row, read again, offers to follow.

Until 2026-09-24 every tap was counted and recorded: 51 of the 298 unfollows in the local base
never happened (the same account "unfollowed" again 17 minutes later, with no re-follow).
These tests drive the real `UnfollowBusiness` list loop on a scripted screen.
"""

import pytest

from fake_follow_list import FakeFacade, FakeScreen, PKG, follow_list_xml, walk_list
from taktik.core.social_media.instagram.actions.business.workflows.unfollow import workflow as unfollow_workflow
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale


@pytest.fixture(autouse=True)
def _french_and_fast(monkeypatch):
    set_active_locale("fr")
    monkeypatch.setattr(unfollow_workflow.time, "sleep", lambda _s: None)
    monkeypatch.setattr(UnfollowBusiness, "confirm_dialog_timeout", 0.0)
    monkeypatch.setattr(UnfollowBusiness, "row_state_timeout", 0.0)
    yield
    set_active_locale(None)


def _business(monkeypatch, *screens):
    screen = FakeScreen(*screens)
    business = UnfollowBusiness(FakeFacade(screen))
    recorded, events = [], []
    business._record_action = lambda username, action, count=1: recorded.append((username, action))
    business._scroll_following_list = lambda: None
    monkeypatch.setattr(unfollow_workflow.IPCEmitter, "emit_unfollow",
                        staticmethod(lambda username, success=True: events.append((username, success))))
    return business, screen, recorded, events


def _dialog(label="Ne plus suivre"):
    return (f'<node index="9" text="{label}" resource-id="{PKG}:id/primary_button" '
            f'class="android.widget.Button" content-desc="" bounds="[100,1800][980,1900]" />')


def test_a_confirmed_unfollow_is_counted_and_recorded(monkeypatch):
    business, _screen, recorded, events = _business(monkeypatch,
        follow_list_xml([("alice.fr", "Suivi(e)")]),
        follow_list_xml([("alice.fr", "Suivre")]),
    )
    stats = walk_list(business, {"max_unfollows": 1})
    assert stats["unfollows_made"] == 1 and stats["unconfirmed"] == 0
    assert recorded == [("alice.fr", "UNFOLLOW")]
    assert events == [("alice.fr", True)]


def test_a_row_that_still_says_following_is_not_counted_nor_retried(monkeypatch):
    screen_before = follow_list_xml([("alice.fr", "Suivi(e)")])
    business, screen, recorded, events = _business(monkeypatch, screen_before, screen_before)
    stats = walk_list(business, {"max_unfollows": 3})
    assert stats["unfollows_made"] == 0 and stats["unconfirmed"] == 1
    assert recorded == []
    assert events == [("alice.fr", False)]
    assert len(screen.taps) == 1  # tapped once, never again


def test_a_private_account_is_confirmed_through_the_localized_dialog(monkeypatch):
    business, screen, recorded, _events = _business(monkeypatch,
        follow_list_xml([("bob_prive", "Suivi(e)")]),
        follow_list_xml([("bob_prive", "Suivi(e)")], extra=_dialog()),
        follow_list_xml([("bob_prive", "Suivre")]),
    )
    # The first tap opens the dialog (screen 2), the dialog tap lands on screen 3.
    stats = walk_list(business, {"max_unfollows": 1})
    assert stats["unfollows_made"] == 1
    assert recorded == [("bob_prive", "UNFOLLOW")]


def test_follow_back_after_the_tap_also_counts(monkeypatch):
    """A fan we unfollow shows "Suivre en retour": the unfollow happened."""
    business, _screen, recorded, _events = _business(monkeypatch,
        follow_list_xml([("carla", "Suivi(e)")]),
        follow_list_xml([("carla", "Suivre en retour")]),
    )
    assert walk_list(business, {"max_unfollows": 1})["unfollows_made"] == 1
    assert recorded == [("carla", "UNFOLLOW")]
