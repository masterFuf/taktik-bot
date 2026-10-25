"""The interaction loop of the runs counts the profiles it visits, acted on or not.

C57 S, Lab `engagement.engage_likers` with like and follow at 0 % (2026-10-25): five profiles opened,
each one through the filters and left without a gesture, and the run said `profiles_visited` 0. Two
counters carry that name, and the loop fed neither for them:

- the run's own figures (`create_workflow_stats`), which the Lab hands back and the feed adds up post
  after post: never fed by the loop;
- the session's counters (`BaseStatsManager`), the « Profiles visited » of the live panel, the rate
  of interaction (acted on / visited) and the pace: fed only for a profile acted on.

After a profile acted on, the loop counts the profile, never its gestures again: the interaction
engine moves the likes, follows, comments and stories at each gesture and records them in the base
(a FOLLOW was once recorded twice, at the tap and after the profile).

A visit, as the followers loop counts it, is a profile that passed the filters, acted on or left by
the plan's draw (it is marked processed in the base either way); a filtered or private profile has
its own counters. The loop now counts it once, in both, whatever the plan drew.

The screen is the real likers sheet of a post liked twice (`likers_sheet_phone`, C57 S, Instagram 410
in English). The host is the loop's own class, built by its constructor on that phone; what happens on
a profile (`_process_profile_on_screen`) and the base's decisions are the only stand-ins.
"""

import time

import pytest

from unit.social_media.instagram.services.likers_sheet_phone import TWO_LIKERS, LikersSheetPhone
from unit.social_media.instagram.services.profile_posts_phone import PKG, capture
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.social_media.instagram.actions.base.base_business.profile_processing import ProfileProcessingResult
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.actions.base.stats import create_workflow_stats
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.common.likers_base import LikersWorkflowBase


@pytest.fixture(autouse=True)
def _english_phone_no_waits(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    monkeypatch.setattr(InstagramWorkflowStateService, "is_profile_skippable",
                        staticmethod(lambda *_a, **_kw: (False, None)))
    set_active_locale("en")
    yield
    set_active_locale(None)


def _run_loop(outcomes):
    """The loop on the sheet of two likers, the profile of each coming back as `outcomes` says.
    Returns the run's figures and the session's counters."""
    phone = LikersSheetPhone(capture(TWO_LIKERS), moves=False)
    host = LikersWorkflowBase(DeviceFacade(CloneAwareDeviceProxy(phone, PKG)))
    host._human_like_delay = lambda *_a, **_kw: None
    host.detection_actions.wait_for_profile_screen = lambda timeout=0: True
    pending = list(outcomes)

    def visit(username, *_a, **_kw):
        result = ProfileProcessingResult(pending.pop(0), username)
        if result.actually_interacted:
            result.interaction_result = {"likes": 1, "actually_interacted": True}
        return result

    host._process_profile_on_screen = visit
    stats = create_workflow_stats("feed")
    host._interact_with_likers_list(stats, {}, max_interactions=5, source_type="FEED", source_name="feed")
    return stats, host.stats_manager.to_dict()


def test_profiles_left_by_the_plan_are_visits_in_both_counters():
    stats, session = _run_loop([ProfileProcessingResult.SKIPPED_PROBABILITY] * 2)

    assert stats["profiles_visited"] == 2
    assert session["profiles_visited"] == 2
    assert session["profiles_interacted"] == 0


def test_a_profile_acted_on_is_one_visit_and_a_filtered_one_none():
    stats, session = _run_loop([ProfileProcessingResult.SUCCESS, ProfileProcessingResult.FILTERED_CRITERIA])

    assert stats["profiles_visited"] == 1
    assert session["profiles_visited"] == 1
    assert session["profiles_interacted"] == 1


def test_after_a_profile_acted_on_its_gestures_are_neither_counted_nor_recorded_again(monkeypatch):
    recorded = []
    monkeypatch.setattr(InstagramWorkflowStateService, "record_individual_actions",
                        staticmethod(lambda *a, **k: recorded.append((a, k)) or True))

    stats, session = _run_loop([ProfileProcessingResult.SUCCESS, ProfileProcessingResult.FILTERED_CRITERIA])

    assert stats["likes_made"] == 1, "the run's figures take the profile's like"
    assert session["likes"] == 0, "the session's like counter moves at the gesture, not here"
    assert recorded == []
