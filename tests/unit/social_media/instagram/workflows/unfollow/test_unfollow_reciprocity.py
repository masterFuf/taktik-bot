"""U6: reciprocity, for real: the followers list says who follows us, and nothing else.

The "don't follow back" category of the followers tab lists FANS (they follow us, we do not
follow them). It used to be read as the accounts WE follow that do not follow back: every fan got
a following row, and every following absent from the category was marked as a mutual. Now the
category only records fans.

The profile of a candidate used to be opened to read a "Follows you" badge before the unfollow, in
the non-followers and mutual modes. No profile of the capture corpus (about 2 800 dumps of 410 and
447, French and English) shows one, a mutual's included (Pixel 3a, 2026-09-27): read, it never said
yes, and the mutual mode refused every candidate. The badge is no longer read; the profile opens
only for the verified and business checks.

The screens are real dumps, anonymized: the followers list of Instagram 410 in English (Pixel 3a,
2026-09-23), our following list of Instagram 410 in French (Pixel 3, sorted by default), and the
profile of an account we follow in French (Pixel 3). Two are DERIVED from them, said where they are
built: the list after the unfollow (the candidate's button reads « Suivre »), and the profile whose
title is the candidate's name.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from fake_follow_list import FakeDetection, FakeFacade, FakeScreen, derived_row_button, walk_list
from taktik.core.social_media.instagram.actions.business.workflows.unfollow import workflow as unfollow_workflow
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.mixins import sync_following
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale


FIXTURES = Path(__file__).parents[2] / "fixtures"
FOLLOWERS_LIST = (FIXTURES / "ig410_en_own_followers_list_categories.xml").read_text(encoding="utf-8")
FOLLOWING_LIST = (FIXTURES / "ig410_fr_following_list_sorted_default.xml").read_text(encoding="utf-8")
FOLLOWED_PROFILE = (FIXTURES / "ig410_fr_profile_following.xml").read_text(encoding="utf-8")
CANDIDATE = "user_2"   # the first row of the following list

# Derived: the list once the candidate is unfollowed, its button offering to follow again.
LIST_AFTER_THE_UNFOLLOW = derived_row_button(FOLLOWING_LIST, CANDIDATE, "Suivre")
# Derived: the profile of an account we follow, with the candidate's name in its title.
CANDIDATE_PROFILE = FOLLOWED_PROFILE.replace('text="name_27"', f'text="{CANDIDATE}"')


@pytest.fixture(autouse=True)
def _french(monkeypatch):
    set_active_locale("fr")
    monkeypatch.setattr(sync_following.time, "sleep", lambda _s: None)
    monkeypatch.setattr(UnfollowBusiness, "confirm_dialog_timeout", 0.0)
    monkeypatch.setattr(UnfollowBusiness, "row_state_timeout", 0.0)
    monkeypatch.setattr(UnfollowBusiness, "profile_open_timeout", 0.0)
    for name in ("emit_unfollow", "emit_stats", "emit_unfollow_plan"):
        monkeypatch.setattr(unfollow_workflow.IPCEmitter, name, staticmethod(lambda *a, **k: None))
    yield
    set_active_locale(None)


class _GraphSpy:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return set() if name.startswith("get_") else "new"
        return record


def test_the_fans_category_records_fans_and_never_a_following(monkeypatch):
    graph = _GraphSpy()
    monkeypatch.setattr(sync_following, "InstagramFollowGraphService", graph)
    business = UnfollowBusiness(FakeFacade(FakeScreen(FOLLOWERS_LIST)))
    business._get_account_id = lambda: 1
    business.nav_actions = SimpleNamespace(navigate_to_profile_tab=lambda: True, open_followers_list=lambda: True)
    business._click_non_followers_category = lambda: True
    business._has_follow_back_row = lambda: True
    business._extract_all_non_followers = lambda: ["fan_one", "fan_two"]

    stats = business.scrape_non_followers_category()

    assert stats["fans_count"] == 2 and stats["non_followers_count"] == 2
    assert stats["mutuals_count"] == 0
    names = [name for name, _args, _kwargs in graph.calls]
    assert names == ["upsert_follower", "upsert_follower"]
    for _name, _args, kwargs in graph.calls:
        assert kwargs["is_following_back"] is False and kwargs["source"] == "fans_category"


def _walk(screens, config):
    screen = FakeScreen(*screens)
    business = UnfollowBusiness(FakeFacade(screen))
    business.detection_actions = FakeDetection(screen, business)
    business.nav_actions.problematic_page_detector = SimpleNamespace(is_action_blocked=lambda: False)
    recorded = []
    business._record_action = lambda username, action, count=1: recorded.append(username)
    stats = walk_list(business, config, names=[CANDIDATE])
    return stats, recorded, screen


def test_the_mutual_mode_unfollows_a_mutual_of_the_followers_list():
    """The candidate came from the followers list (a mutual). Its profile opens for the verified
    check only, and nothing on it refuses the unfollow: it used to answer `not_mutual` to every
    candidate, the badge that says "follows you" not being on any profile."""
    stats, recorded, screen = _walk([FOLLOWING_LIST, CANDIDATE_PROFILE, FOLLOWING_LIST, LIST_AFTER_THE_UNFOLLOW],
                                    {"unfollow_mode": "mutual", "skip_verified": True})

    assert stats["profile_refusals"] == {}
    assert recorded == [CANDIDATE] and stats["unfollows_made"] == 1
    assert screen.presses == ["back"]            # back from the profile


def test_a_profile_opened_for_its_check_is_a_profile_visit(monkeypatch):
    """The live panel counts the profiles the unfollow checked: one `instagram_profile_visit` per
    profile that opened, none when no profile opens."""
    visits = []
    monkeypatch.setattr(unfollow_workflow.IPCEmitter, "emit_profile_visit", staticmethod(visits.append))

    _walk([FOLLOWING_LIST, CANDIDATE_PROFILE, FOLLOWING_LIST, LIST_AFTER_THE_UNFOLLOW],
          {"unfollow_mode": "non-followers", "skip_verified": True})
    assert visits == [CANDIDATE]

    _walk([FOLLOWING_LIST, LIST_AFTER_THE_UNFOLLOW],
          {"unfollow_mode": "non-followers", "skip_verified": False, "skip_business": False})
    assert visits == [CANDIDATE]


@pytest.mark.parametrize("mode", ["non-followers", "mutual"])
def test_without_an_account_kind_to_check_no_profile_is_opened(mode):
    """The reciprocity modes used to open every candidate's profile for the badge."""
    stats, recorded, screen = _walk([FOLLOWING_LIST, LIST_AFTER_THE_UNFOLLOW],
                                    {"unfollow_mode": mode, "skip_verified": False, "skip_business": False})

    assert recorded == [CANDIDATE] and stats["profile_refusals"] == {}
    assert screen.presses == []                  # no profile, no way back to take
