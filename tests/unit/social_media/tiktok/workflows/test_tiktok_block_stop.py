"""TikTok stops at the FIRST refusal, on every writing path, and says why.

Before this, TikTok had no block detection at all: its `detection.rate_limit` entries ("too many",
"trop de") matched half the captions and nothing called them. A refused like was counted, the
next gesture was tried on the same video, and the run went on to its cap. Now every gesture that
writes is followed by one look (`look_for_action_block` on `DetectionActions.is_action_blocked`);
seeing the refusal sets the run's latch, the gesture is not counted, the next ones are not tried,
and the run ends with `completion_reason = action_blocked`.

The detector below keeps the production contract: it reads the screen and, when TikTok refuses,
sets the latch itself.
"""

import types

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.tiktok.actions.atomic.detection.detection_actions import DetectionActions
from taktik.core.social_media.tiktok.actions.business.workflows._internal.base_video_workflow import (
    BaseVideoWorkflow,
)
from taktik.core.social_media.tiktok.actions.business.workflows._internal.base_workflow import (
    BaseTikTokWorkflow,
)
from taktik.core.social_media.tiktok.actions.business.workflows.followers.interaction import (
    VideoInteractionMixin,
)

_QUIET = type("L", (), {m: (lambda *a, **k: None)
                         for m in ("info", "debug", "warning", "success", "error")})()


class _Refusing:
    """The production detector's contract: seeing the refusal sets the run's latch."""

    def __init__(self, refuse_after=1):
        self.looks = 0
        self.refuse_after = refuse_after

    def is_action_blocked(self):
        self.looks += 1
        if self.looks >= self.refuse_after:
            run_halt.demander_arret(run_halt.ACTION_BLOCKED, "tiktok (Too many requests)")
            return True
        return False


class _Clicks:
    def __init__(self):
        self.tapped = []

    def click_like_button(self):
        self.tapped.append("like")
        return True

    def click_video_follow_button(self):
        self.tapped.append("follow")
        return True

    def click_favorite_button(self):
        self.tapped.append("favorite")
        return True


class _Config:
    like_probability = 1.0
    follow_probability = 1.0
    favorite_probability = 1.0
    max_likes_per_session = 50
    max_follows_per_session = 50


class _Stats:
    videos_liked = 0
    users_followed = 0
    videos_favorited = 0
    videos_commented = 0
    completion_reason = ""


class _Feed(BaseVideoWorkflow):
    """A video feed without a phone: its clicks land, its detector says whether TikTok refused."""

    def __init__(self, detector):
        self.config = _Config()
        self.stats = _Stats()
        self.click = _Clicks()
        self.detection = detector
        self._actions_since_pause = 0
        self._on_like_callback = None
        self._on_follow_callback = None
        self.logger = _QUIET

    def _send_stats_update(self):
        pass


def _video():
    return {"author": "demo_creator", "is_liked": False, "is_favorited": False}


def test_a_refused_like_is_not_counted_and_nothing_else_is_tried():
    feed = _Feed(_Refusing(refuse_after=1))

    feed._decide_and_execute_actions(_video())

    assert feed.click.tapped == ["like"], "a follow or a favourite tried after the refusal"
    assert feed.stats.videos_liked == 0
    assert feed.stats.users_followed == 0


def test_the_feed_ends_with_the_block_as_its_reason():
    feed = _Feed(_Refusing(refuse_after=2))

    feed._decide_and_execute_actions(_video())

    assert feed.click.tapped == ["like", "follow"]
    assert feed.stats.videos_liked == 1 and feed.stats.users_followed == 0
    assert feed._check_limits_reached() is True
    assert feed.stats.completion_reason == "action_blocked"


def test_a_screen_that_says_nothing_lets_every_gesture_through():
    feed = _Feed(_Refusing(refuse_after=99))

    feed._decide_and_execute_actions(_video())

    assert feed.click.tapped == ["like", "follow", "favorite"]
    assert run_halt.arret_demande() is None


# --- the followers / target-profiles road -------------------------------------------------------


class _Walker(VideoInteractionMixin, BaseTikTokWorkflow):
    def __init__(self, detector):
        self.config = types.SimpleNamespace(
            like_probability=1.0, favorite_probability=1.0, comment_probability=1.0,
            share_probability=0.0, max_likes_per_session=50, max_comments_per_session=50,
        )
        self.stats = types.SimpleNamespace(likes=0, favorites=0, comments=0)
        self.detection = detector
        self._current_profile_username = "demo_creator"
        self.tried = []
        self.recorded = []
        self.logger = _QUIET

    def _is_video_already_liked(self):
        return False

    def _try_like_video(self):
        self.tried.append("like")
        return True

    def _try_favorite_video(self):
        self.tried.append("favorite")
        return True

    def _try_comment_video(self, comment_text=None, ai_metadata=None):
        self.tried.append("comment")
        return True

    def _send_action(self, *args):
        pass

    def _record_interaction(self, kind, username):
        self.recorded.append(kind)

    def _send_stats_update(self):
        pass


def test_on_a_profile_video_a_refused_like_is_not_recorded_and_ends_the_video():
    walker = _Walker(_Refusing(refuse_after=1))

    walker._interact_with_current_video()

    assert walker.tried == ["like"]
    assert walker.stats.likes == 0
    assert walker.recorded == [], "a refused like written as an interaction"


# --- the detection itself -----------------------------------------------------------------------


def _screen(*nodes):
    body = "".join(nodes)
    return (f'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            f'<node class="android.widget.FrameLayout" text="" resource-id="" bounds="[0,0][1080,2340]">'
            f'{body}</node></hierarchy>')


def _text(text, rid="", focusable="false"):
    rid_attr = f"com.zhiliaoapp.musically:id/{rid}" if rid else ""
    return (f'<node class="android.widget.TextView" text="{text}" resource-id="{rid_attr}" '
            f'content-desc="" focusable="{focusable}" bounds="[40,1000][1040,1080]"/>')


def _detection_on(xml):
    detection = DetectionActions.__new__(DetectionActions)
    detection.device = types.SimpleNamespace(dump_hierarchy=lambda compressed=False: xml)
    detection.logger = _QUIET
    return detection


def test_tiktok_refusing_the_account_is_seen_and_sets_the_latch():
    detection = _detection_on(_screen(_text("You're tapping too fast. Take a break.", rid="toast")))

    assert detection.is_action_blocked() is True
    assert (run_halt.arret_demande() or {}).get("code") == "action_blocked"


def test_the_same_words_in_a_caption_prove_nothing():
    detection = _detection_on(_screen(_text("Too many requests from my followers lol", rid="desc")))

    assert detection.is_action_blocked() is False
    assert run_halt.arret_demande() is None


def test_one_word_of_a_caption_is_not_a_refusal():
    """The old entries were single words ("too many", "trop de"): they matched captions."""
    detection = _detection_on(_screen(_text("too many cats", rid="toast")))

    assert detection.is_action_blocked() is False
