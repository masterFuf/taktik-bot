"""The account's excluded terms where a gesture is decided (`actions/base/base_business/term_exclusion.py`).

A profile term in a profile's handle, name or bio leaves the profile out at the profile pipeline, before
any AI call or gesture, and at the interaction engine for the callers that skip the pipeline. A post term
in a framed post's caption leaves the post out; so does a caption that could not be read whole.

The posts are real home feeds of Instagram 410 in French (Pixel 3a, 1080x2220), anonymized, read as
production reads a dump (`framed_post_context`); their words are the anonymizer's (`name_11`), the terms
are taken from them or invented.
"""

from types import SimpleNamespace

import pytest

from taktik.core.contract.shared import (
    BIOGRAPHY,
    CAPTION,
    EXCLUDED_TERM,
    POST_CAPTION_UNREAD,
    POST_EXCLUDED_TERM,
    USERNAME,
)
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.shared.filtering.excluded_terms import ExcludedTerms
from taktik.core.social_media.instagram.actions.atomic.scroll.post_reading import PostReadingMixin
from taktik.core.social_media.instagram.actions.base.base_business import profile_processing, term_exclusion
from taktik.core.social_media.instagram.actions.base.base_business.interaction_engine import InteractionEngineMixin
from taktik.core.social_media.instagram.actions.base.base_business.profile_processing import (
    ProfileProcessingMixin,
    ProfileProcessingResult,
)
from taktik.core.social_media.instagram.actions.base.base_business.term_exclusion import post_verdict
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
#: The framed post shown whole, its caption untruncated: « name_7 name_8 name_9, name_10 la name_11
#: name_12 de name_13. », by name_4.
WHOLE_POST = "ig410_fr_feed_two_captions.xml"
#: The framed post's header alone above the tabs: its caption is under the screen.
HEADER_ABOVE_TABS = "ig410_fr_feed_caption_with_hashtags.xml"
#: The framed post's caption truncated (« … plus »), a sliver above the tab bar.
TRUNCATED_CAPTION = "ig410_fr_feed_previous_caption_above_header.xml"


class _Reader(PostReadingMixin):
    screen_height = 2220
    device = object()

    class logger:  # noqa: N801 - minimal stand-in
        @staticmethod
        def debug(_msg):
            return None


def _read(name: str, reframed: bool = True):
    context = _Reader().framed_post_context(parse_ui_dump((FIXTURES / name).read_text(encoding="utf-8")))
    return {**context, "reframed": reframed}


@pytest.fixture
def said(monkeypatch):
    lines = []
    monkeypatch.setattr(term_exclusion.IPCEmitter, "emit_term_exclusion",
                        staticmethod(lambda *args: lines.append(args)))
    return lines


# ------------------------------------------------------------------------------------ a post


def test_a_post_term_at_the_start_of_a_word_of_the_caption_leaves_the_post_out():
    verdict = post_verdict(_read(WHOLE_POST), ExcludedTerms(post_terms=("Name_11",)))

    assert (verdict.reason, verdict.term, verdict.place, verdict.author) == (POST_EXCLUDED_TERM, "Name_11", CAPTION, "name_4")


def test_a_longer_word_of_the_caption_that_holds_the_term_further_in_keeps_the_post():
    verdict = post_verdict(_read(WHOLE_POST), ExcludedTerms(post_terms=("ame_11",)))

    assert verdict.allowed
    assert verdict.identity, "the post the caption was read on, for the gesture that follows"


def test_a_profile_term_in_the_authors_handle_leaves_the_post_out():
    verdict = post_verdict(_read(WHOLE_POST), ExcludedTerms(profile_terms=("ame4",)))

    assert (verdict.reason, verdict.term, verdict.place, verdict.author) == (EXCLUDED_TERM, "ame4", USERNAME, "name_4")


def test_a_caption_under_the_bottom_of_the_screen_is_not_read_and_the_post_is_left_out():
    context = _read(HEADER_ABOVE_TABS)
    assert context["caption_text"] == "" and context["post_ends_on_screen"] is False

    verdict = post_verdict(context, ExcludedTerms(post_terms=("zorvak",)))

    assert verdict.reason == POST_CAPTION_UNREAD


def test_a_caption_still_truncated_is_not_read_and_the_post_is_left_out():
    verdict = post_verdict(_read(TRUNCATED_CAPTION), ExcludedTerms(post_terms=("zorvak",)))

    assert verdict.reason == POST_CAPTION_UNREAD


def test_a_reading_that_lost_the_post_or_no_post_framed_leaves_the_post_out():
    terms = ExcludedTerms(post_terms=("zorvak",))

    assert post_verdict(_read(WHOLE_POST, reframed=False), terms).reason == POST_CAPTION_UNREAD
    assert post_verdict(None, terms).reason == POST_CAPTION_UNREAD


def test_profile_terms_alone_ask_nothing_of_the_caption():
    assert post_verdict(_read(TRUNCATED_CAPTION), ExcludedTerms(profile_terms=("zorvak",))).allowed
    assert post_verdict(None, ExcludedTerms(profile_terms=("zorvak",))).allowed


def test_without_terms_nothing_is_read(said):
    host = SimpleNamespace(scroll_actions=None, session_manager=SimpleNamespace(excluded_terms=ExcludedTerms()))

    assert term_exclusion.check_post_terms(host, author_hint="name_4").allowed
    assert said == []


def test_a_post_left_out_is_said_with_its_reason_its_term_and_where(said):
    reader = SimpleNamespace(read_framed_caption=lambda: _read(WHOLE_POST))
    host = SimpleNamespace(scroll_actions=reader,
                           session_manager=SimpleNamespace(excluded_terms=ExcludedTerms(post_terms=("name_11",))))

    assert not term_exclusion.check_post_terms(host).allowed
    assert said == [(POST_EXCLUDED_TERM, "name_4", "name_11", CAPTION)]


# ------------------------------------------------------------------------------------ a profile


class _Pipeline(ProfileProcessingMixin):
    """The shared profile pipeline, its readers and its engine as stand-ins; the run's session holds the terms."""

    def __init__(self, terms: ExcludedTerms, profile: dict):
        quiet = lambda *a, **k: None  # noqa: E731
        self.logger = SimpleNamespace(debug=quiet, info=quiet, success=quiet, warning=quiet, error=quiet)
        self.session_manager = SimpleNamespace(excluded_terms=terms)
        self.profile_business = SimpleNamespace(get_complete_profile_info=lambda **_k: dict(profile))
        self.filtering_business = SimpleNamespace(
            apply_comprehensive_filter=lambda *_a: {"suitable": True, "reasons": []})
        self.counted = []
        self.stats_manager = SimpleNamespace(increment=lambda key, *_a: self.counted.append(key))
        self.recorded = []
        self.engine_calls = []

    def _perform_interactions_on_profile(self, username, config, profile_data=None):
        self.engine_calls.append(username)
        return {"actually_interacted": True}

    def _record_filtered_in_db(self, username, reason, *_args):
        self.recorded.append((username, reason))


@pytest.fixture
def quiet_pipeline(monkeypatch):
    actions = []
    monkeypatch.setattr(profile_processing.IPCEmitter, "emit_profile_visit", staticmethod(lambda *_a: None))
    monkeypatch.setattr(profile_processing.IPCEmitter, "emit_action",
                        staticmethod(lambda action, username, data=None: actions.append((action, username, data))))
    monkeypatch.setattr(profile_processing.InstagramWorkflowStateService, "mark_profile_as_processed",
                        staticmethod(lambda *a, **k: True))
    return actions


def test_a_profile_term_in_the_middle_of_the_handle_leaves_the_profile_out_before_any_gesture(quiet_pipeline, said):
    pipeline = _Pipeline(ExcludedTerms(profile_terms=("zorvak",)),
                         {"username": "leazorvak", "full_name": "Léa", "biography": "", "followers_count": 300})

    result = pipeline._process_profile_on_screen("leazorvak", {}, source_type="FOLLOWER")

    assert result.status == ProfileProcessingResult.FILTERED_CRITERIA
    assert result.filter_reasons == [EXCLUDED_TERM]
    assert pipeline.engine_calls == [], "a gesture was planned on a profile left out"
    assert pipeline.recorded == [("leazorvak", EXCLUDED_TERM)]
    assert "profiles_filtered" in pipeline.counted
    assert said == [(EXCLUDED_TERM, "leazorvak", "zorvak", USERNAME)]
    assert ("filter", "leazorvak", {"reasons": [EXCLUDED_TERM], "followers_count": 300}) in quiet_pipeline


def test_a_profile_term_starting_a_word_of_the_bio_leaves_the_profile_out(quiet_pipeline, said):
    pipeline = _Pipeline(ExcludedTerms(profile_terms=("zorvak",)),
                         {"username": "lea.photo", "biography": "Ambassadrice Zorvakshop", "followers_count": 300})

    result = pipeline._process_profile_on_screen("lea.photo", {}, source_type="FOLLOWER")

    assert result.status == ProfileProcessingResult.FILTERED_CRITERIA
    assert said == [(EXCLUDED_TERM, "lea.photo", "zorvak", BIOGRAPHY)]


def test_a_profile_without_the_term_goes_on_to_the_engine(quiet_pipeline, said):
    pipeline = _Pipeline(ExcludedTerms(profile_terms=("zorvak",)),
                         {"username": "lea.photo", "biography": "Ambassadrice superzorvak", "followers_count": 300})

    result = pipeline._process_profile_on_screen("lea.photo", {}, source_type="FOLLOWER")

    assert result.status == ProfileProcessingResult.SUCCESS
    assert pipeline.engine_calls == ["lea.photo"]
    assert said == []


def test_the_engine_makes_no_gesture_on_a_profile_left_out_reached_without_the_pipeline(said):
    # The Feed visits a post's author straight through the engine.
    engine = object.__new__(InteractionEngineMixin)
    engine.logger = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None, error=lambda *a: None,
                                    debug=lambda *a: None)
    engine.session_manager = SimpleNamespace(excluded_terms=ExcludedTerms(profile_terms=("zorvak",)))
    engine._determine_interactions_from_config = lambda _config: pytest.fail("a plan was drawn")

    result = engine._perform_interactions_on_profile("lea_zorvak", {}, profile_data={"username": "lea_zorvak"})

    assert result["actually_interacted"] is False
    assert (result["likes"], result["follows"], result["comments"], result["stories"]) == (0, 0, 0, 0)
    assert said == [(EXCLUDED_TERM, "lea_zorvak", "zorvak", USERNAME)]
