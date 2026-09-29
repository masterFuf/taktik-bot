"""A detection of the Lab answers yes OR no; only a screen it could not read is a failure.

A detection asks the screen one question (is a post open, is the video liked, is the author
followed...). The Lab reported the production function's False as a failed action, so the auto-test
was red on a correct "no" (`detection.is_post_open` on the feed, `tt.detection.is_liked` on a video
nobody liked: Pixel 3a, 2026-09-27). Now the action succeeds with the answer in `details.found`, the
production function called as it is. A "no" is an answer only on a screen of the app that could be
read: an empty dump or another app in front fails the action, never "no"; an exception still fails
it (the runner catches it).

The screens are real dumps, anonymized: TikTok 43.1.4 in French, Instagram 410 in English, read by
uiautomator2's own `XPathEntry`.
"""

import pytest
from uiautomator2.xpath import XPathEntry

from bridges.tools.lab.actions.instagram import ACTION_REGISTRY as INSTAGRAM_ACTIONS
from bridges.tools.lab.actions.instagram import register_actions as register_instagram
from bridges.tools.lab.actions.tiktok import ACTION_REGISTRY as TIKTOK_ACTIONS
from bridges.tools.lab.actions.tiktok import register_actions as register_tiktok
from bridges.tools.lab.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from bridges.tools.lab.action_test.bundles.tiktok import (
    build_tiktok_action_bundle,
    create_tiktok_device_facade,
)
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale as instagram_locale
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale as tiktok_locale
from unit.paths import CORE

SOCIAL = CORE / "tests/unit/social_media"
TIKTOK = SOCIAL / "tiktok" / "fixtures"
INSTAGRAM = SOCIAL / "instagram" / "fixtures"

#: A For You video nobody on the account liked, its author not followed.
FOR_YOU = (TIKTOK / "tt4314_fr_for_you_video.xml").read_text(encoding="utf-8")
#: A For You video the account liked.
LIKED = (TIKTOK / "tt4314_fr_liked_video.xml").read_text(encoding="utf-8")
#: The Instagram home feed on a carousel post: no post is "open" there.
IG_FEED = (INSTAGRAM / "ig410_en_home_feed_carousel_post.xml").read_text(encoding="utf-8")
#: A post opened in the viewer.
IG_POST = (INSTAGRAM / "ig410_en_profile_posts_next_photo_framed.xml").read_text(encoding="utf-8")


class _Phone:
    """uiautomator2 as the Lab touches it: `xpath()` and a dump of one screen."""

    wait_timeout = 1.0

    def __init__(self, xml, package):
        self.xml, self.package = xml, package
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def app_current(self):
        return {"package": self.package, "activity": "demo.Activity"}


@pytest.fixture(autouse=True)
def locales():
    tiktok_locale("fr")
    instagram_locale("en")
    register_tiktok()
    register_instagram()
    yield
    tiktok_locale(None)
    instagram_locale(None)


def _tiktok(xml):
    return build_tiktok_action_bundle(create_tiktok_device_facade(_Phone(xml, "com.zhiliaoapp.musically")))


def _instagram(xml, package="com.instagram.android"):
    return build_instagram_action_bundle(create_instagram_device_facade(_Phone(xml, package)))


@pytest.mark.parametrize("action_id", ["tt.detection.is_liked", "tt.detection.is_followed",
                                       "tt.detection.is_live_preview"])
def test_a_tiktok_detection_answering_no_on_a_video_succeeds_with_the_answer(action_id):
    result = TIKTOK_ACTIONS[action_id](_tiktok(FOR_YOU), {})
    assert result["success"] is True
    assert result["details"] == {"found": False}
    assert result["message"] == f"{action_id}: no"


def test_a_tiktok_detection_answering_yes_succeeds_with_the_answer():
    result = TIKTOK_ACTIONS["tt.detection.is_liked"](_tiktok(LIKED), {})
    assert result["success"] is True
    assert result["details"] == {"found": True}
    assert result["message"] == "tt.detection.is_liked: yes"


def test_an_empty_dump_is_no_answer_never_a_no():
    result = TIKTOK_ACTIONS["tt.detection.is_liked"](_tiktok(""), {})
    assert result["success"] is False
    assert result["details"] == {"found": None}
    assert "screen unreadable" in result["message"]


def test_instagram_is_post_open_on_the_feed_is_a_no_and_a_success():
    result = INSTAGRAM_ACTIONS["detection.is_post_open"](_instagram(IG_FEED), {})
    assert (result["success"], result["details"]) == (True, {"found": False})


def test_instagram_is_post_open_in_the_viewer_is_a_yes():
    result = INSTAGRAM_ACTIONS["detection.is_post_open"](_instagram(IG_POST), {})
    assert (result["success"], result["details"]) == (True, {"found": True})


def test_another_app_in_front_is_no_answer_for_instagram():
    # TikTok on screen: Instagram's "no post open" would be true of a screen that is not Instagram's.
    result = INSTAGRAM_ACTIONS["detection.is_post_open"](_instagram(FOR_YOU, "com.zhiliaoapp.musically"), {})
    assert result["success"] is False
    assert result["details"] == {"found": None}


def test_an_exception_of_the_production_function_is_not_turned_into_an_answer():
    bundle = _tiktok(FOR_YOU)

    def broken(*_a, **_k):
        raise RuntimeError("uiautomator2 lost the phone")

    bundle.video_detector.is_video_liked = broken
    with pytest.raises(RuntimeError):
        TIKTOK_ACTIONS["tt.detection.is_liked"](bundle, {})


def test_a_production_answer_of_none_is_no_answer():
    bundle = _tiktok(FOR_YOU)
    bundle.video_detector.is_live_preview = lambda *_a, **_k: None
    result = TIKTOK_ACTIONS["tt.detection.is_live_preview"](bundle, {})
    assert (result["success"], result["details"]) == (False, {"found": None})


#: Every yes/no question of the screen the Lab asks, answered through `@detection` (one way).
INSTAGRAM_DETECTIONS = {
    "account.detect_connected_accounts", "account.detect_login_screen", "account.is_logged_out",
    "detection.is_action_blocked", "detection.is_home_screen", "detection.is_post_open",
    "detection.is_profile_screen", "detection.is_reel_post", "engagement.has_likes",
    "notifications.is_follow_requests_open", "notifications.is_open", "popups.is_comment_open",
    "popups.is_likers_open", "popups.is_share_sheet_open", "post.is_liked",
    "profile.is_follow_available", "profile.is_unfollow_available", "scraping.is_list_end_reached",
    "scraping.is_list_limited", "scraping.is_suggestions_section", "story.has_profile_story",
    "story.is_ad", "story.is_open", "suggestions.is_discover_screen", "suggestions.probe_carousel",
}
TIKTOK_DETECTIONS = {
    "tt.detection.is_action_blocked", "tt.detection.is_ad", "tt.detection.is_followed",
    "tt.detection.is_for_you", "tt.detection.is_inbox", "tt.detection.is_liked",
    "tt.detection.is_live_preview", "tt.popups.has_collections", "tt.popups.has_comments",
    "tt.popups.has_popup",
}


def test_every_yes_no_question_of_the_lab_is_answered_the_same_way():
    from bridges.tools.lab.actions import instagram, tiktok

    assert instagram.DETECTIONS == INSTAGRAM_DETECTIONS
    assert tiktok.DETECTIONS == TIKTOK_DETECTIONS
    assert INSTAGRAM_DETECTIONS <= set(INSTAGRAM_ACTIONS) and TIKTOK_DETECTIONS <= set(TIKTOK_ACTIONS)


@pytest.mark.parametrize("production, answer", [("login_form", True), ("profile_picker", True), (None, False)],
                         ids=["login-form", "saved-profiles", "neither-login-screen"])
def test_the_login_screen_detection_reads_the_three_answers_of_production(monkeypatch, production, answer):
    """`InstagramLogin._read_login_screen` answers the login form, the saved profiles, or neither
    (the home feed, found on the Pixel 3a on 2026-09-28, where the Lab said "no answer"). The first
    two are login screens; the screen is still checked to be Instagram's and readable."""
    from taktik.core.social_media.instagram.actions.account.login import InstagramLogin

    monkeypatch.setattr(InstagramLogin, "_read_login_screen", lambda self: production)
    result = INSTAGRAM_ACTIONS["account.detect_login_screen"](_instagram(IG_FEED), {})
    assert (result["success"], result["details"]) == (True, {"found": answer})
