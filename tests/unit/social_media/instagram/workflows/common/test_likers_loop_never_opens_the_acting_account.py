"""The interaction loop of the runs never opens the profile of the account it acts as.

Seen on the C57 S (Instagram 410 in English, 2026-10-25): a Feed run likes the post, then walks its
likers, and the account it acts as is now one of them. `LikersWorkflowBase._interact_with_likers_list`
opened that row like any other: its own profile came up, the way back did not find the sheet again
(three tries) and the post was left with its other likers unwalked. The account is known to the run
before its first gesture (`automation.active_username`, read off its own profile when the run
starts; the Lab's `account` parameter): its row is passed without a tap, as the followers loop
already passes it (`own_account`), and the list goes on to its end.

The screen is the real likers sheet of a post liked twice (`likers_sheet_phone`, C57 S, Instagram 410
in English); one of its two likers stands for the acting account. The host is the loop's own class,
built by its constructor on that phone; what happens on a profile (`_process_profile_on_screen`) and
the base's decisions are the only stand-ins.
"""

import time
from types import SimpleNamespace

import pytest

from unit.social_media.instagram.services.likers_sheet_phone import TWO_LIKERS, LikersSheetPhone
from unit.social_media.instagram.services.profile_posts_phone import PKG, capture
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.social_media.instagram.actions.base.base_business.profile_processing import ProfileProcessingResult
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.actions.base.stats import create_workflow_stats
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.common import likers_base
from taktik.core.social_media.instagram.workflows.common.likers_base import LikersWorkflowBase


@pytest.fixture(autouse=True)
def _english_phone_no_waits(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    set_active_locale("en")
    yield
    set_active_locale(None)


@pytest.fixture(autouse=True)
def _base_knows_nobody(monkeypatch):
    monkeypatch.setattr(InstagramWorkflowStateService, "is_profile_skippable",
                        staticmethod(lambda *_a, **_kw: (False, None)))


@pytest.fixture
def decisions(monkeypatch):
    """The loop's ledger: one `follower_decision` per row met."""
    seen = []
    monkeypatch.setattr(likers_base, "emit_step", lambda step, **fields: seen.append((step, fields)))
    return seen


def _run_loop(phone, acting_username):
    """The loop on the phone, for a run acting as `acting_username`. Returns the profiles opened."""
    automation = SimpleNamespace(active_account_id=1, current_session_id=None, active_username=acting_username)
    host = LikersWorkflowBase(DeviceFacade(CloneAwareDeviceProxy(phone, PKG)), automation=automation)
    host._human_like_delay = lambda *_a, **_kw: None
    host.detection_actions.wait_for_profile_screen = lambda timeout=0: True
    visits = []

    def visit(username, *_a, **_kw):
        visits.append(username)
        return ProfileProcessingResult(ProfileProcessingResult.FILTERED_CRITERIA, username)

    host._process_profile_on_screen = visit
    stats = create_workflow_stats("feed")
    host._interact_with_likers_list(stats, {}, max_interactions=5, source_type="FEED", source_name="feed")
    return visits, stats


def test_the_acting_account_among_the_likers_is_passed_without_a_tap(decisions):
    phone = LikersSheetPhone(capture(TWO_LIKERS), moves=False)
    acting, other = phone.likers_shown()

    visits, stats = _run_loop(phone, acting)

    assert visits == [other]
    assert len(phone.taps) == 1, f"taps: {phone.taps}"
    assert stats["users_found"] == 1
    own = [fields for step, fields in decisions if fields.get("target") == acting]
    assert [(fields["action"], fields["reason"]) for fields in own] == [("skipped", "own_account")]


def test_the_list_still_ends_on_its_own_end_after_passing_the_acting_account():
    phone = LikersSheetPhone(capture(TWO_LIKERS), moves=False)
    acting, _other = phone.likers_shown()

    _run_loop(phone, acting)

    drags_up = len(phone.likers_after_each_drag_up)
    assert drags_up == 2, f"{drags_up} drag(s) up a list of two likers that no longer moves"


def test_the_acting_account_is_recognised_whatever_its_case_and_at_sign():
    phone = LikersSheetPhone(capture(TWO_LIKERS), moves=False)
    acting, other = phone.likers_shown()

    visits, _stats = _run_loop(phone, f"@{acting.upper()}")

    assert visits == [other]


def test_a_run_that_does_not_know_its_account_yet_opens_every_liker():
    phone = LikersSheetPhone(capture(TWO_LIKERS), moves=False)

    visits, _stats = _run_loop(phone, None)

    assert sorted(visits) == phone.likers_shown()
