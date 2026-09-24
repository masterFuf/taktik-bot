"""The first "Try again later" ends the run, wherever it is seen (2026-09-24).

Before: the detector SAW Instagram's rate-limit dialog, closed it, and the run acted again
right after -- the gesture that turns a temporary limit into a lasting restriction. Only the
followers workflow, when its list was out of reach, called it a block and stopped.

Now the detector sets the run's stop lock (`run_halt.ACTION_BLOCKED`) as soon as it sees the
dialog, `should_continue` turns it into the `action_blocked` stop reason, the engine reads the
lock on entry, and each gesture that writes (like, comment, follow, story like) is followed by
one look. The dialog is proven by its own words: its three ids are the chassis of every
Instagram alert, the contacts request included. The detector used here is the real one; only
the phone is fake, and its screens mirror the real captures (a dialog over the screen behind).
"""

import collections
import random
import types

import pytest

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.core.social_media.instagram.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.instagram.workflows.management.session.session import SessionManager
from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import (
    InteractionEngineMixin,
)
from taktik.core.social_media.instagram.actions.core.base_business.config_parsing import (
    ConfigParsingMixin,
)
from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import (
    LikeOrchestration,
)
import taktik.core.social_media.instagram.actions.business.workflows.feed.workflow as feed_module
from taktik.core.social_media.instagram.actions.business.workflows.feed.workflow import FeedBusiness
from taktik.core.social_media.instagram.actions.business.common.workflow_defaults import FEED_DEFAULTS
from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation

IG = "com.instagram.android:id"

_BEHIND = (
    f'<node class="android.widget.TextView" text="bob" resource-id="{IG}/row_feed_photo_profile_name" '
    'bounds="[40,300][300,360]"/>'
    f'<node class="android.widget.TextView" text="{{bio}}" resource-id="{IG}/profile_header_bio_text" '
    'bounds="[40,400][1040,520]"/>'
)


def _screen(dialog=None, bio=""):
    """A screen as the dump gives it: what is behind, then the alert on top, if any."""
    alert = ""
    if dialog is not None:
        headline, subtext = dialog
        alert = (
            '<node class="android.widget.FrameLayout" package="com.instagram.android" bounds="[60,800][1020,1500]">'
            f'<node class="android.widget.TextView" text="{headline}" '
            f'resource-id="{IG}/igds_alert_dialog_headline" bounds="[100,850][980,930]"/>'
            f'<node class="android.widget.TextView" text="{subtext}" '
            f'resource-id="{IG}/igds_alert_dialog_subtext" bounds="[100,950][980,1150]"/>'
            f'<node class="android.widget.Button" text="OK" '
            f'resource-id="{IG}/igds_alert_dialog_primary_button" bounds="[100,1250][980,1350]"/>'
            '</node>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
        '<node class="android.widget.FrameLayout" package="com.instagram.android" bounds="[0,0][1080,2400]">'
        + _BEHIND.replace("{bio}", bio) + alert +
        '</node></hierarchy>'
    )


BLOCK_FR = ("Réessayer plus tard", "Nous limitons la fréquence de certaines actions que vous pouvez "
            "effectuer sur Instagram pour protéger notre communauté. Contactez-nous si vous pensez "
            "que nous avons fait une erreur.")
BLOCK_EN = ("Try Again Later", "We limit how often you can do certain things on Instagram to "
            "protect our community. Tell us if you think we made a mistake.")
CONTACTS_FR = ("Autoriser Instagram à accéder à vos contacts ?", "Vos contacts seront synchronisés.")
UPDATE_ALERT = ("Mise à jour disponible", "Installez la dernière version.")


@pytest.fixture(autouse=True)
def _lock_lifted():
    before = active_locale()
    set_active_locale("fr")
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()
    set_active_locale(before)


class _Phone:
    """What the detector reads: `screen()` decides what is on it, and dumps are counted."""

    def __init__(self, screen=lambda: _screen()):
        self._screen = screen
        self.dumps = 0

    def dump_hierarchy(self, *a, **k):
        self.dumps += 1
        return self._screen()


def _blocked_when(condition, dialog=BLOCK_FR):
    return _Phone(lambda: _screen(dialog) if condition() else _screen())


# ─────────────────────────────────────────── the detector: its words prove it, its ids do not

@pytest.mark.parametrize("dialog", [BLOCK_FR, BLOCK_EN])
def test_seeing_the_dialog_sets_the_lock(dialog):
    detector = ProblematicPageDetector(_Phone(lambda: _screen(dialog)))

    assert detector.is_action_blocked() is True
    lock = run_halt.arret_demande()
    assert lock["code"] == run_halt.ACTION_BLOCKED
    assert lock["evidence"] == "words"


def test_an_ordinary_screen_sets_nothing():
    detector = ProblematicPageDetector(_Phone())

    assert detector.is_action_blocked() is False
    assert run_halt.arret_demande() is None


def test_the_contacts_request_is_not_a_block():
    """Same three alert ids as the block: taken alone, they stopped the run -- and the popup
    handler then tapped its primary button, which UPLOADS the address book."""
    detector = ProblematicPageDetector(_Phone(lambda: _screen(CONTACTS_FR)))

    assert detector.is_action_blocked() is False
    assert run_halt.arret_demande() is None


def test_the_popup_handler_no_longer_takes_the_contacts_request_for_a_block(monkeypatch):
    detector = ProblematicPageDetector(_Phone(lambda: _screen(CONTACTS_FR)))
    closed = []
    monkeypatch.setattr(detector, "_close_problematic_page",
                        lambda page_type, methods: closed.append(page_type) or True)

    result = detector.detect_and_handle_problematic_pages()

    assert "try_again_later_page" not in closed
    assert not (isinstance(result, dict) and result.get("soft_ban"))
    assert run_halt.arret_demande() is None


def test_another_alert_in_a_language_we_read_is_not_a_block():
    detector = ProblematicPageDetector(_Phone(lambda: _screen(UPDATE_ALERT)))

    assert detector.is_action_blocked() is False


def test_in_a_language_we_cannot_read_the_ids_are_all_there_is():
    """A missed block costs the account more than a stopped run: the ids count, and say so."""
    set_active_locale(None)
    detector = ProblematicPageDetector(_Phone(lambda: _screen(UPDATE_ALERT)))

    assert detector.is_action_blocked() is True
    assert run_halt.arret_demande()["evidence"] == "ids_only"


def test_the_words_count_in_the_dialog_only_not_in_a_bio_behind_it():
    screen = _screen(UPDATE_ALERT, bio="Try Again Later, we limit how often we post")
    detector = ProblematicPageDetector(_Phone(lambda: screen))

    assert detector.is_action_blocked() is False


def test_closing_the_dialog_no_longer_lets_the_run_act_again(monkeypatch):
    """The popup handler closes the dialog, as before -- but the lock is set BEFORE the close,
    so the run stops at its next `should_continue` instead of liking again."""
    detector = ProblematicPageDetector(_Phone(lambda: _screen(BLOCK_FR)))
    lock_at_close = []
    monkeypatch.setattr(detector, "_close_problematic_page",
                        lambda page_type, methods: lock_at_close.append(run_halt.arret_demande()) or True)

    result = detector.detect_and_handle_problematic_pages()

    assert result["soft_ban"] is True
    assert lock_at_close and lock_at_close[0]["code"] == run_halt.ACTION_BLOCKED


# ─────────────────────────────────────────────────────────────── the session reads it

def test_the_session_names_the_stop_action_blocked():
    session = SessionManager({"session_settings": {"session_duration_minutes": 60}})
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")

    keep_going, reason = session.should_continue()

    assert keep_going is False
    assert reason.code == "action_blocked"


def test_a_stop_before_the_first_step_still_closes_the_session():
    """A block seen while closing the launch popups: the loop was never entered, the session
    stayed open and the bridge announced "completed" with no reason."""
    automation = object.__new__(InstagramAutomation)
    automation.config = {"actions": [{"type": "feed"}]}
    automation.logger = types.SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None)
    automation.update_session_manager_config = lambda: None
    automation.helpers = types.SimpleNamespace(initialize_session=lambda: 1)
    automation.session_manager = SessionManager({"session_settings": {"session_duration_minutes": 60}})
    finalized = []
    automation._finalize_session = lambda status, reason: finalized.append((status, reason))
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")

    automation.run_workflow()

    assert len(finalized) == 1
    assert finalized[0][1].code == "action_blocked"


# ─────────────────────────────────────────────── the engine: lock on entry, look after writes

class _Logger:
    def __init__(self):
        self.lines = []

    def _log(self, *a, **k):
        self.lines.append(str(a[0]) if a else "")

    debug = info = warning = error = success = _log


class _LikeBusiness:
    """The like loop. The real one (LikeOrchestration) looks after each like itself and sets
    the lock on a refusal: `refuse` stands for that."""

    def __init__(self, refuse=False):
        self.calls = 0
        self._refuse = refuse

    def like_profile_posts(self, *a, **k):
        self.calls += 1
        if self._refuse:
            run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page", evidence="words")
        return {"posts_liked": 1, "posts_commented": 0}


class _ClickActions:
    def __init__(self):
        self.follow_calls = 0

    def follow_user(self, username):
        self.follow_calls += 1
        return True

    def get_follow_button_state(self):
        return "follow"


class _ScrollActions:
    def scroll_to_top(self, *a, **k):
        stop_condition = k.get("stop_condition")
        return bool(stop_condition()) if stop_condition else True


class _DetectionActions:
    def has_unseen_profile_story(self, *a, **k):
        return False


class _Engine(InteractionEngineMixin, ConfigParsingMixin):
    """Real engine and real detector; the phone, the like loop and the follow tap are fakes."""

    def __init__(self, phone, like_business, click_actions):
        self.logger = _Logger()
        self.like_business = like_business
        self.click_actions = click_actions
        self.scroll_actions = _ScrollActions()
        self.detection_actions = _DetectionActions()
        self.nav_actions = types.SimpleNamespace(problematic_page_detector=ProblematicPageDetector(phone))

    def _emit_like_event(self, *a, **k):
        pass

    def _emit_follow_event(self, *a, **k):
        pass

    def _record_action(self, *a, **k):
        pass

    def _handle_follow_suggestions_popup(self):
        pass

    def _recover_from_blocking_modal(self, *a, **k):
        return None


def _cfg():
    return {
        "like_probability": 1.0,
        "follow_probability": 1.0,
        "comment_probability": 0.0,
        "story_probability": 0.0,
        "story_like_probability": 0.0,
        "min_likes_per_profile": 1,
    }


def _follow_first(monkeypatch):
    # The engine draws the follow phase: below 0.35 it runs first, on arrival.
    monkeypatch.setattr(random, "random", lambda: 0.0)


def _follow_last(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.99)


def test_a_lock_set_before_the_profile_means_no_write_on_it(monkeypatch):
    """A block seen on the previous row, or during the navigation here: the row loops used to
    open the next profile and like or follow it before their next check."""
    _follow_first(monkeypatch)
    clicks, likes = _ClickActions(), _LikeBusiness()
    engine = _Engine(_Phone(), likes, clicks)
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")

    engine._perform_interactions_on_profile("alice", _cfg(), profile_data=None)

    assert clicks.follow_calls == 0
    assert likes.calls == 0


def test_a_refused_follow_ends_the_profile_before_the_likes(monkeypatch):
    _follow_first(monkeypatch)
    clicks, likes = _ClickActions(), _LikeBusiness()
    engine = _Engine(_blocked_when(lambda: clicks.follow_calls > 0), likes, clicks)

    engine._perform_interactions_on_profile("alice", _cfg(), profile_data=None)

    assert clicks.follow_calls == 1
    assert likes.calls == 0
    assert run_halt.arret_demande()["code"] == run_halt.ACTION_BLOCKED


def test_a_refusal_in_the_like_loop_ends_the_profile_before_the_follow(monkeypatch):
    _follow_last(monkeypatch)
    clicks, likes = _ClickActions(), _LikeBusiness(refuse=True)
    phone = _Phone()
    engine = _Engine(phone, likes, clicks)

    engine._perform_interactions_on_profile("alice", _cfg(), profile_data=None)

    assert likes.calls == 1
    assert clicks.follow_calls == 0
    assert phone.dumps == 0, "the lock answers: no second dump for the same refusal"


def test_without_the_dialog_the_profile_runs_as_before_for_one_dump(monkeypatch):
    _follow_last(monkeypatch)
    clicks, likes = _ClickActions(), _LikeBusiness()
    phone = _Phone()
    engine = _Engine(phone, likes, clicks)

    result = engine._perform_interactions_on_profile("alice", _cfg(), profile_data=None)

    assert likes.calls == 1
    assert clicks.follow_calls == 1
    assert result["follows"] == 1
    assert run_halt.arret_demande() is None
    assert phone.dumps == 1, "one look after the tapped follow; the like loop looks on its own"


def test_the_check_costs_nothing_when_no_follow_was_tapped():
    clicks = _ClickActions()
    phone = _Phone()
    engine = _Engine(phone, _LikeBusiness(), clicks)
    plan = types.SimpleNamespace(do_follow=True)

    tapped = engine._do_follow("alice", plan, {"follow_button_state": "following"}, {"follows": 0})

    assert tapped is False
    assert clicks.follow_calls == 0
    assert phone.dumps == 0


# ────────────────────────────────────────── the like loop: one look after each like and comment

def _orchestration(phone, liked=True):
    orch = object.__new__(LikeOrchestration)
    orch.logger = _Logger()
    orch.nav_actions = types.SimpleNamespace(problematic_page_detector=ProblematicPageDetector(phone))
    orch.gestures = []

    def _like():
        orch.gestures.append("like")
        return liked

    def _comment(*a, **k):
        orch.gestures.append("comment")
        return True

    orch.like_current_post = _like
    orch._comment_current_post = _comment
    return orch


def test_a_refused_like_is_seen_before_the_comment():
    phone = _Phone()
    orch = _orchestration(phone)
    phone._screen = lambda: _screen(BLOCK_FR) if orch.gestures else _screen()

    liked, commented = orch._run_engagement_sequence(["like", "comment"], "alice", [], "generic", {})

    assert orch.gestures == ["like"]
    assert commented is False
    assert run_halt.arret_demande()["code"] == run_halt.ACTION_BLOCKED


def test_a_refused_like_that_reads_as_failed_is_still_seen():
    phone = _Phone(lambda: _screen(BLOCK_FR))
    orch = _orchestration(phone, liked=False)

    orch._run_engagement_sequence(["like", "comment"], "alice", [], "generic", {})

    assert run_halt.arret_demande()["code"] == run_halt.ACTION_BLOCKED


def test_the_sequence_without_the_dialog_looks_once_per_gesture():
    phone = _Phone()
    orch = _orchestration(phone)

    liked, commented = orch._run_engagement_sequence(["like", "comment"], "alice", [], "generic", {})

    assert (liked, commented) == (True, True)
    assert phone.dumps == 2


# ────────────────────────────────────────────────────────── the feed loop reads the lock

class _Stats:
    def increment(self, *a, **k):
        pass


def _feed(phone, gestures):
    feed = object.__new__(FeedBusiness)
    feed.logger = _Logger()
    feed.default_config = {**FEED_DEFAULTS}
    feed.session_manager = None
    feed.automation = None
    feed.stats_manager = _Stats()
    feed.nav_actions = types.SimpleNamespace(
        navigate_to_home=lambda: True,
        problematic_page_detector=ProblematicPageDetector(phone),
    )
    feed.scroll_actions = types.SimpleNamespace(
        human_reading_pause=lambda **k: None,
        scroll_feed_to_next_post=lambda **k: {"on_feed": True},
    )
    feed._is_sponsored_post = lambda: False
    feed._is_reel_post = lambda: False
    feed._get_current_post_author = lambda: "bob"
    feed.has_feed_suggestions_carousel = lambda: False
    feed._like_current_post = lambda record_as=None: gestures.append("like") or True
    feed.comment_business = types.SimpleNamespace(
        comment_on_post=lambda **k: gestures.append("comment") or {"commented": True})
    return feed


_FEED_RUN = {
    "max_interactions": 5,
    "max_posts_to_check": 5,
    "like_percentage": 100,
    "comment_percentage": 100,
    "view_feed_stories": False,
    "follow_suggestions": False,
    "min_post_likes": 0,
    "max_post_likes": 0,
    "capture_ads": False,
    "interact_with_post_author": False,
    "interact_with_post_likers": False,
}


@pytest.fixture
def _feed_cards(monkeypatch):
    cards = []
    monkeypatch.setattr(feed_module.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(feed_module.IPCEmitter, "emit_feed_decision",
                        lambda author, action, reason=None: cards.append((author, action)))
    return cards


def test_the_feed_stops_on_the_first_refused_like_before_commenting(_feed_cards):
    gestures = []
    feed = _feed(_Phone(), gestures)
    feed.nav_actions.problematic_page_detector.device._screen = (
        lambda: _screen(BLOCK_FR) if gestures else _screen())

    feed.interact_with_feed(dict(_FEED_RUN))

    assert gestures == ["like"]
    assert run_halt.arret_demande()["code"] == run_halt.ACTION_BLOCKED
    assert _feed_cards == [("bob", "like")], "the liked post keeps its copilot card"


def test_the_feed_reads_a_lock_set_elsewhere(_feed_cards):
    """A lost phone or a block seen during navigation: the feed loop never read the lock."""
    gestures = []
    feed = _feed(_Phone(), gestures)
    run_halt.demander_arret(run_halt.DEVICE_DISCONNECTED, "le telephone ne repond plus")

    feed.interact_with_feed(dict(_FEED_RUN))

    assert gestures == []


def test_the_feed_without_the_dialog_likes_and_comments_as_before(_feed_cards):
    gestures = []
    feed = _feed(_Phone(), gestures)

    feed.interact_with_feed(dict(_FEED_RUN))

    assert gestures == ["like", "comment"] * 5
    assert run_halt.arret_demande() is None


# ───────────────────────── second review: an alert is never accepted, and every loop stops

from taktik.core.social_media.instagram.ui.selectors.shell.blocking_states import (  # noqa: E402
    PROBLEMATIC_PAGE_SELECTORS,
)


def _recording_detector(screen):
    detector = ProblematicPageDetector(_Phone(lambda: screen))
    calls = {"close": [], "click": []}
    detector._close_problematic_page = lambda page_type, methods: calls["close"].append(page_type) or True
    detector._click_button_from_selectors = lambda selectors, name: calls["click"].append(selectors) or True
    return detector, calls


def test_an_alert_read_on_its_ids_alone_is_never_accepted():
    """Unknown language: the ids are all there is. The run stops; nothing is tapped, since the
    primary button of an alert we cannot read may accept anything."""
    set_active_locale(None)
    detector, calls = _recording_detector(_screen(UPDATE_ALERT))

    result = detector.detect_and_handle_problematic_pages()

    assert result["soft_ban"] is True and result["closed"] is False
    assert calls == {"close": [], "click": []}
    lock = run_halt.arret_demande()
    assert lock["evidence"] == "ids_only" and "ids_only" in lock["detail"]


def test_the_contacts_request_is_dismissed_by_its_cancel_button_only():
    """Never by its primary button, and never handed to the Android permission pattern, whose
    first gesture taps "Allow"."""
    detector, calls = _recording_detector(_screen(CONTACTS_FR))

    result = detector.detect_and_handle_problematic_pages()

    assert result["page_type"] == "instagram_alert" and result["soft_ban"] is False
    assert calls["click"] == [PROBLEMATIC_PAGE_SELECTORS.alert_cancel_button_selectors]
    assert calls["close"] == []
    assert run_halt.arret_demande() is None


def test_the_real_dialog_is_still_closed_by_its_ok_after_the_lock():
    detector, calls = _recording_detector(_screen(BLOCK_FR))

    detector.detect_and_handle_problematic_pages()

    assert calls["close"] == ["try_again_later_page"]
    assert run_halt.arret_demande()["evidence"] == "words"


def test_the_hashtag_post_is_not_commented_after_a_refused_like():
    from taktik.core.social_media.instagram.actions.business.workflows.hashtag.workflow import (
        HashtagBusiness,
    )

    gestures = []
    phone = _Phone(lambda: _screen(BLOCK_FR) if gestures else _screen())
    workflow = object.__new__(HashtagBusiness)
    workflow.logger = _Logger()
    workflow.stats_manager = _Stats()
    workflow.nav_actions = types.SimpleNamespace(problematic_page_detector=ProblematicPageDetector(phone))
    workflow.like_business = types.SimpleNamespace(like_current_post=lambda **k: gestures.append("like") or True)
    workflow.comment_business = types.SimpleNamespace(
        comment_on_post=lambda **k: gestures.append("comment") or {"commented": True})
    stats = {"likes_made": 0, "comments_made": 0}

    workflow._engage_post_itself({"like_percentage": 100, "comment_percentage": 100}, stats, "bob")

    assert gestures == ["like"]
    assert run_halt.arret_demande()["code"] == run_halt.ACTION_BLOCKED


def test_the_hashtag_loop_does_not_open_another_post_after_a_block():
    from taktik.core.social_media.instagram.actions.business.workflows.hashtag.workflow import (
        HashtagBusiness,
    )

    workflow = object.__new__(HashtagBusiness)
    workflow.logger = _Logger()

    def _never(*a, **k):
        raise AssertionError("no post is opened after a block")

    workflow._find_first_valid_post = _never
    workflow.session_manager = None
    workflow.stats_manager = types.SimpleNamespace(display_final_stats=lambda **k: None)
    finalized = []
    workflow.automation = types.SimpleNamespace(helpers=types.SimpleNamespace(
        finalize_session=lambda status, reason: finalized.append((status, reason.code))))
    plan = types.SimpleNamespace(max_posts=3, is_noop=False, describe=lambda: "test plan")
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")
    stats = collections.defaultdict(int)

    workflow._run_interaction_plan("travel", plan, {"min_likes": 0, "max_likes": 10 ** 9},
                                   stats, account_id=None)

    assert stats["stop_reason"].code == "action_blocked"
    # Closed as what it is: a run Instagram stopped did not complete.
    assert finalized and finalized[0][1] == "action_blocked" and finalized[0][0] != "COMPLETED"


def test_a_blocked_run_neither_pays_for_nor_loses_the_next_profile(monkeypatch):
    """The AI hooks wrap the engine and pay before its gate; the profile was then marked
    processed with nothing done. The gate now sits before them."""
    from taktik.core.social_media.instagram.actions.core.base_business import profile_processing
    from taktik.core.social_media.instagram.actions.core.base_business.profile_processing import (
        ProfileProcessingMixin, ProfileProcessingResult,
    )

    marked, interactions = [], []
    monkeypatch.setattr(profile_processing.IPCEmitter, "emit_profile_visit", lambda *a, **k: None)
    monkeypatch.setattr(profile_processing.InstagramWorkflowStateService, "mark_profile_as_processed",
                        lambda *a, **k: marked.append(a))

    class _Processor(ProfileProcessingMixin):
        pass

    processor = _Processor()
    processor.logger = _Logger()
    processor.stats_manager = _Stats()

    def _extract(**k):
        # The block is seen while the profile is read (a popup check on the way).
        run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")
        return {"is_private": False, "followers_count": 10}

    processor.profile_business = types.SimpleNamespace(get_complete_profile_info=_extract)
    processor.filtering_business = types.SimpleNamespace(
        apply_comprehensive_filter=lambda *a, **k: {"suitable": True})
    processor._relationship_skip_reason = lambda *a, **k: None
    processor._perform_interactions_on_profile = lambda *a, **k: interactions.append(a) or {}

    result = processor._process_profile_on_screen("alice", {}, source_type="FOLLOWER")

    assert interactions == []
    assert marked == []
    assert result.status == ProfileProcessingResult.ERROR_INTERACTION


def test_no_suggestion_is_visited_after_a_block():
    from taktik.core.social_media.instagram.actions.business.workflows.common.suggestion_visit import (
        visit_suggestions,
    )

    reached = []
    surface = types.SimpleNamespace(reach=lambda: reached.append(1) or True)
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")

    result = visit_suggestions(surface, max_profiles=3)

    assert result["stop_reason"] == "action_blocked"
    assert reached == []


def test_a_refused_comment_is_neither_recorded_nor_followed_by_a_share_sheet(monkeypatch):
    from taktik.core.social_media.instagram.actions.business.actions.comment import action as action_module
    from taktik.core.social_media.instagram.actions.business.actions.comment.action import CommentAction

    monkeypatch.setattr(action_module, "validate_comment", lambda *a, **k: True)
    monkeypatch.setattr(action_module.time, "sleep", lambda *a, **k: None)
    comment = object.__new__(CommentAction)
    comment.logger = _Logger()
    comment.default_config = {"comment_delay_range": (0, 0)}
    comment.session_manager = None
    recorded, closed = [], []
    comment._is_comment_composer_open = lambda: True
    comment._dismiss_share_sheet_if_open = lambda: False
    comment._type_comment = lambda text: True
    comment._post_comment = lambda: True
    comment._stop_if_action_blocked = lambda username, action: True
    comment._close_comment_popup = lambda: closed.append(1) or True
    comment._record_action = lambda *a, **k: recorded.append(a)
    comment._attach_post_url = lambda *a, **k: recorded.append("share sheet")

    stats = comment.comment_on_post(comment_text="Superbe", username="alice")

    assert stats["blocked"] is True and stats["commented"] is False
    assert recorded == []
    assert closed == [1]
