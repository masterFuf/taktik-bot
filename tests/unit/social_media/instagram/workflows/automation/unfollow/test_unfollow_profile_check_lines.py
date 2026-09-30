"""The lines a profile check of the unfollow prints: a visit, then the profile read, then its outcome.

The unfollow opens a candidate's profile for the verified and business checks. Since 2026-09-28 it
says so (`instagram_profile_visit`), and the Agent panel opened a card for each such visit that
never closed: every workflow that opens a profile follows the visit with the profile read
(`profile_captured`, which closes the card and gives both panels the picture), and the unfollow did
not. Seen on a real run of a Pixel 6a (2026-09-28): 24 cards spinning, the unfollows done.

What a check prints, on each path:

- the profile opens: the visit, then at once the profile read, with the picture the production
  extractor crops (`extract_profile_image`, the one Target uses), whatever the check decides;
- no profile opens (no check asked, or the profile never showed): neither line;
- the row is gone from the list when the check comes back: the decision says why the account is
  kept, as every other refusal on screen does (`unfollow_decision`).

The screens are the real dumps of `test_unfollow_reciprocity.py` (our following list and the profile
of an account we follow, Instagram 410 in French, Pixel 3), anonymized; the screens derived from
them are said where they are built. The picture needs a screenshot, which no dump carries: the fake
detection returns a marker, and the test checks it is the one the line carries.
"""

from types import SimpleNamespace

import pytest

from fake_follow_list import FakeDetection, FakeFacade, FakeScreen, derived_row_button, walk_list
from taktik.core.social_media.instagram.workflows.automation.unfollow import workflow as unfollow_workflow
from taktik.core.social_media.instagram.workflows.automation.unfollow.mixins import decision
from taktik.core.social_media.instagram.workflows.automation.unfollow.mixins import sync_following
from taktik.core.social_media.instagram.workflows.automation.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from unit.paths import CORE


FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
FOLLOWING_LIST = (FIXTURES / "ig410_fr_following_list_sorted_default.xml").read_text(encoding="utf-8")
FOLLOWED_PROFILE = (FIXTURES / "ig410_fr_profile_following.xml").read_text(encoding="utf-8")
CANDIDATE = "user_2"   # the first row of the following list

# Derived: the list once the candidate is unfollowed, its button offering to follow again.
LIST_AFTER_THE_UNFOLLOW = derived_row_button(FOLLOWING_LIST, CANDIDATE, "Suivre")
# Derived: the list back from the profile, the candidate's row button gone (the row is lost).
LIST_WITHOUT_THE_ROW = derived_row_button(FOLLOWING_LIST, CANDIDATE, None)
# Derived: the profile of an account we follow, with the candidate's name in its title.
CANDIDATE_PROFILE = FOLLOWED_PROFILE.replace('text="name_27"', f'text="{CANDIDATE}"')

PICTURE = FakeDetection.AVATAR


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


@pytest.fixture
def lines(monkeypatch):
    """The visit and profile-read lines the check prints, in order, and the decisions."""
    printed = []
    monkeypatch.setattr(decision.IPCEmitter, "emit_profile_visit",
                        staticmethod(lambda username: printed.append(("visit", username))))
    monkeypatch.setattr(decision.IPCEmitter, "emit_profile_captured",
                        staticmethod(lambda username, profile_data=None, profile_pic_base64=None:
                                     printed.append(("profile_read", username, profile_data, profile_pic_base64))))
    monkeypatch.setattr(unfollow_workflow, "emit_step",
                        lambda category, action=None, target=None, **detail:
                        printed.append((category, action, target, detail.get("reason"))))
    return printed


def _walk(screens, config, detection=None):
    screen = FakeScreen(*screens)
    business = UnfollowBusiness(FakeFacade(screen))
    business.detection_actions = FakeDetection(screen, business)
    for name, answer in (detection or {}).items():
        setattr(business.detection_actions, name, answer)
    business.nav_actions.problematic_page_detector = SimpleNamespace(is_action_blocked=lambda: False)
    unfollowed = []
    business._record_action = lambda username, action, count=1: unfollowed.append(username)
    stats = walk_list(business, config, names=[CANDIDATE])
    return stats, unfollowed


def test_a_checked_profile_is_read_right_after_its_visit(lines):
    """The profile opens, nothing refuses the unfollow: the visit, then the profile read with the
    picture the production extractor cropped; no profile data, the check reads none."""
    stats, unfollowed = _walk([FOLLOWING_LIST, CANDIDATE_PROFILE, FOLLOWING_LIST, LIST_AFTER_THE_UNFOLLOW],
                              {"unfollow_mode": "non-followers", "skip_verified": True})

    assert unfollowed == [CANDIDATE] and stats["profile_refusals"] == {}
    assert lines == [("visit", CANDIDATE), ("profile_read", CANDIDATE, None, PICTURE)]


@pytest.mark.parametrize("config, detection, refusal", [
    ({"skip_verified": True}, {"is_verified_account": lambda: True}, "verified"),
    ({"skip_verified": False, "skip_business": True}, {"is_business_account": lambda: True}, "business"),
])
def test_a_profile_kept_by_its_check_is_read_too(lines, config, detection, refusal):
    """The check refuses the unfollow: the visit is closed the same way, then the decision says
    why the account is kept."""
    stats, unfollowed = _walk([FOLLOWING_LIST, CANDIDATE_PROFILE, FOLLOWING_LIST],
                              {"unfollow_mode": "non-followers", **config}, detection)

    assert unfollowed == [] and stats["profile_refusals"] == {refusal: 1}
    assert lines == [("visit", CANDIDATE), ("profile_read", CANDIDATE, None, PICTURE),
                     ("unfollow_decision", "skip", CANDIDATE, refusal)]


def test_a_check_that_fails_on_the_profile_still_closes_the_visit(lines):
    """A check that raises keeps the account (`profile_unreadable`): the visit was closed before."""
    def unreadable():
        raise RuntimeError("the screen could not be read")

    stats, unfollowed = _walk([FOLLOWING_LIST, CANDIDATE_PROFILE, FOLLOWING_LIST],
                              {"unfollow_mode": "non-followers", "skip_verified": True},
                              {"is_verified_account": unreadable})

    assert unfollowed == [] and stats["profile_refusals"] == {"profile_unreadable": 1}
    assert lines == [("visit", CANDIDATE), ("profile_read", CANDIDATE, None, PICTURE),
                     ("unfollow_decision", "skip", CANDIDATE, "profile_unreadable")]


def test_no_profile_opened_no_visit_and_no_profile_read(lines):
    """Without an account kind to check, the profile is not opened: neither line."""
    stats, unfollowed = _walk([FOLLOWING_LIST, LIST_AFTER_THE_UNFOLLOW],
                              {"unfollow_mode": "non-followers", "skip_verified": False, "skip_business": False})

    assert unfollowed == [CANDIDATE]
    assert lines == []


def test_a_profile_that_never_showed_is_not_a_visit(lines):
    """The tap on the row leaves the list on screen: no visit, no profile read, the decision only."""
    stats, unfollowed = _walk([FOLLOWING_LIST, FOLLOWING_LIST],
                              {"unfollow_mode": "non-followers", "skip_verified": True})

    assert unfollowed == [] and stats["profile_refusals"] == {"profile_unreadable": 1}
    assert lines == [("unfollow_decision", "skip", CANDIDATE, "profile_unreadable")]


def test_a_row_lost_after_the_profile_says_why_the_account_is_kept(lines):
    """Back from the profile, the candidate's row cannot be read: the account is kept (`row_lost`),
    and the decision says so, like every other refusal on screen. It used to be only in the log."""
    stats, unfollowed = _walk([FOLLOWING_LIST, CANDIDATE_PROFILE, LIST_WITHOUT_THE_ROW],
                              {"unfollow_mode": "non-followers", "skip_verified": True})

    assert unfollowed == [] and stats["profile_refusals"] == {"row_lost": 1}
    assert lines == [("visit", CANDIDATE), ("profile_read", CANDIDATE, None, PICTURE),
                     ("unfollow_decision", "skip", CANDIDATE, "row_lost")]
