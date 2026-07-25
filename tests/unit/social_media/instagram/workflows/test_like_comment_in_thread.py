"""Liking a comment must never become unliking one.

The gesture is the same tap in both directions: Instagram's heart toggles. So the only thing
standing between "engage a commenter" and "remove a like from their comment" is the state
check — these tests hold it in place.
"""

import types

import pytest

from taktik.core.social_media.instagram.actions.business.actions.comment.action import CommentAction

THREAD = """
<hierarchy>
  <node class="android.view.ViewGroup" bounds="[0,334][576,547]" content-desc="">
    <node class="android.view.ViewGroup" bounds="[131,346][492,500]" content-desc="taktik_r2d2 ">
      <node class="android.widget.Button" bounds="[145,346][243,371]" content-desc="" text="taktik_r2d2"/>
    </node>
    <node class="android.widget.Button" bounds="[492,334][576,424]" content-desc="{state}"/>
  </node>
</hierarchy>
"""


class _Device:
    def __init__(self, xml, tap_ok=True):
        self._xml = xml
        self.taps = []
        self._tap_ok = tap_ok

    def dump_hierarchy(self, *_a, **_k):
        return self._xml

    def human_tap(self, bounds, **_k):
        if not self._tap_ok:
            return None
        self.taps.append(tuple(bounds))
        return (bounds[0] + 1, bounds[1] + 1)


class _Session:
    def __init__(self):
        self.recorded = []

    def record_action(self, action_type, success=True, source=None):
        self.recorded.append((action_type, success))


def _action(xml, comments_open=True, tap_ok=True, session=None):
    """A CommentAction with its device seams replaced — no __init__, no real device."""
    from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS

    act = CommentAction.__new__(CommentAction)
    act.device = _Device(xml, tap_ok=tap_ok)
    act.logger = types.SimpleNamespace(
        debug=lambda *a, **k: None, info=lambda *a, **k: None, success=lambda *a, **k: None,
        warning=lambda *a, **k: None, error=lambda *a, **k: None,
    )
    act.post_selectors = POST_COMMENTS_SELECTORS
    act.scroll_actions = types.SimpleNamespace(scroll_down=lambda: None)
    act.session_manager = session
    act._is_comments_view_open = lambda: comments_open
    act._human_like_delay = lambda _kind: None
    act.recorded = []
    act._record_action = lambda username, kind, count=1, **kw: act.recorded.append((username, kind, count))
    return act


@pytest.fixture(autouse=True)
def _english_locale():
    from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
    set_active_locale("en")


NOT_LIKED = THREAD.format(state="Tap to like comment")
ALREADY_LIKED = THREAD.format(state="1 like. Double tap to unlike comment and press and hold")


# ── The happy path ──────────────────────────────────────────────────────────

def test_a_comment_is_liked_and_recorded_as_its_own_interaction_type():
    session = _Session()
    act = _action(NOT_LIKED, session=session)

    result = act.like_comment_in_thread("taktik_r2d2")

    assert result["success"] is True
    assert act.device.taps == [(492, 334, 576, 424)]
    # COMMENT_LIKE, not LIKE: a like on a comment is not a like on a post.
    assert act.recorded == [("taktik_r2d2", "COMMENT_LIKE", 1)]
    assert session.recorded == [("like_comment", True)]


def test_the_whole_control_is_handed_to_the_humanised_tap():
    act = _action(NOT_LIKED)
    act.like_comment_in_thread("taktik_r2d2")
    left, top, right, bottom = act.device.taps[0]
    assert right > left and bottom > top  # a box, not a fixed point


# ── Never unliking ──────────────────────────────────────────────────────────

def test_an_already_liked_comment_is_left_alone():
    session = _Session()
    act = _action(ALREADY_LIKED, session=session)

    result = act.like_comment_in_thread("taktik_r2d2")

    assert result["success"] is False
    assert result["skipped_reason"] == "already_liked"
    assert act.device.taps == []        # the tap would have UNLIKED it
    assert act.recorded == []           # and nothing is claimed in the stats
    assert session.recorded == []


def test_an_unreadable_control_is_treated_as_untouchable():
    """Locale drift, or an Instagram relabel: if we cannot tell liked from not-liked, we
    do not gamble — a missed like costs nothing, a wrong tap is visible to the target."""
    act = _action(THREAD.format(state="Etwas ganz anderes"))
    result = act.like_comment_in_thread("taktik_r2d2")
    assert result["success"] is False
    assert act.device.taps == []


# ── Refusals ────────────────────────────────────────────────────────────────

def test_nothing_happens_when_the_thread_is_not_open():
    act = _action(NOT_LIKED, comments_open=False)
    result = act.like_comment_in_thread("taktik_r2d2")
    assert result["success"] is False
    assert act.device.taps == []


def test_an_absent_commenter_is_reported_not_found_after_scrolling():
    act = _action(NOT_LIKED)
    result = act.like_comment_in_thread("someone_else", max_scrolls=2)
    assert result["skipped_reason"] == "not_found"
    assert act.device.taps == []


def test_an_empty_username_is_refused_without_touching_the_screen():
    act = _action(NOT_LIKED)
    assert act.like_comment_in_thread("")["success"] is False
    assert act.device.taps == []


def test_a_failed_tap_is_not_recorded_as_a_like():
    session = _Session()
    act = _action(NOT_LIKED, tap_ok=False, session=session)

    result = act.like_comment_in_thread("taktik_r2d2")

    assert result["success"] is False
    assert act.recorded == []
    assert session.recorded == []


def test_a_broken_dump_does_not_raise():
    act = _action("not xml at all")
    assert act.like_comment_in_thread("taktik_r2d2", max_scrolls=1)["success"] is False
