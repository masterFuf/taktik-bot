"""Answering a comment must land UNDER that comment.

Instagram threads a reply by the "@username " mention it prefills when the row's own Reply
affordance is tapped. Lose that mention and the reply silently becomes an ordinary top-level
comment addressed to nobody — published, counted, and wrong.
"""

import types

import pytest

from taktik.core.social_media.instagram.actions.business.actions.comment.action import CommentAction

THREAD = """
<hierarchy>
  <node class="android.view.ViewGroup" bounds="[0,185][576,302]" content-desc="">
    <node class="android.view.ViewGroup" bounds="[84,197][492,255]" content-desc="dianeou38 ">
      <node class="android.widget.Button" bounds="[98,197][189,222]" content-desc="" text="dianeou38"/>
    </node>
    <node class="android.widget.Button" bounds="[98,255][170,302]" content-desc="Reply" text="Reply"/>
  </node>
</hierarchy>
"""


class _Field:
    """The comment composer, as uiautomator2 exposes it."""

    def __init__(self, text=""):
        self.exists = True
        self._text = text

    def get_text(self):
        return self._text

    def set_text(self, value):
        self._text = value

    def click(self):
        pass


class _Device:
    def __init__(self, xml, field, tap_ok=True):
        self._xml = xml
        self._field = field
        self.taps = []
        self._tap_ok = tap_ok

    def dump_hierarchy(self, *_a, **_k):
        return self._xml

    def xpath(self, _selector):
        return self._field

    def human_tap(self, bounds, **_k):
        if not self._tap_ok:
            return None
        self.taps.append(tuple(bounds))
        return (bounds[0], bounds[1])


def _action(field=None, xml=THREAD, comments_open=True, tap_ok=True,
            typed_ok=True, sent_ok=True, records=None):
    from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS

    act = CommentAction.__new__(CommentAction)
    act.device = _Device(xml, field if field is not None else _Field("@dianeou38 "), tap_ok=tap_ok)
    act.logger = types.SimpleNamespace(
        debug=lambda *a, **k: None, info=lambda *a, **k: None, success=lambda *a, **k: None,
        warning=lambda *a, **k: None, error=lambda *a, **k: None,
    )
    act.post_selectors = POST_COMMENTS_SELECTORS
    act.default_config = {'comment_delay_range': (0, 0)}
    act.scroll_actions = types.SimpleNamespace(scroll_down=lambda: None)
    act.session_manager = None
    act._is_comments_view_open = lambda: comments_open
    act._human_like_delay = lambda _kind: None
    act._close_comment_popup = lambda: True
    act._type_comment = lambda _text: typed_ok
    act._post_comment = lambda: sent_ok
    act._get_account_id = lambda: 1
    act._get_session_id = lambda: 2
    act.actions = records if records is not None else []
    act._record_action = lambda u, k, c=1, **kw: act.actions.append((u, k, kw.get('content')))
    return act


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    """Capture what would be written to posted_comments instead of writing it."""
    written = {}

    def _record(**kwargs):
        written.update(kwargs)
        return 42

    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.comment.action"
        ".InstagramPostedComments.record",
        staticmethod(lambda **kw: _record(**kw)),
    )
    return written


# ── The happy path ──────────────────────────────────────────────────────────

def test_a_reply_taps_the_rows_own_reply_button(_no_db):
    act = _action()

    result = act.reply_to_comment_in_thread("dianeou38", "Merci pour ce retour !")

    assert result["success"] is True
    assert act.device.taps == [(98, 255, 170, 302)]  # dianeou38's Reply, not a neighbour's


def test_a_reply_is_stored_as_a_reply_and_keeps_who_it_answers(_no_db):
    act = _action()

    act.reply_to_comment_in_thread("dianeou38", "Merci !", reply_to_text="Super post")

    assert _no_db["kind"] == "reply"
    assert _no_db["target_username"] == "dianeou38"   # the COMMENTER, not the post author
    assert _no_db["reply_to_username"] == "dianeou38"
    assert _no_db["reply_to_text"] == "Super post"
    assert _no_db["comment_text"] == "Merci !"


def test_a_reply_is_ledgered_as_a_comment_with_its_text(_no_db):
    """A reply IS a published text: it consumes the comment budget and shows in the drill-down."""
    act = _action()
    act.reply_to_comment_in_thread("dianeou38", "Merci !")
    assert act.actions == [("dianeou38", "COMMENT", "Merci !")]


# ── The mention is the thread link ──────────────────────────────────────────

def test_a_wiped_mention_is_restored_before_sending(_no_db):
    """The typing helper falls back to set_text, which REPLACES the field — that fallback
    erases the prefilled "@dianeou38 " and the reply would land as a top-level comment."""
    field = _Field("Merci !")  # mention gone: what set_text leaves behind
    act = _action(field=field)

    act.reply_to_comment_in_thread("dianeou38", "Merci !")

    assert field.get_text() == "@dianeou38 Merci !"


def test_an_intact_mention_is_left_untouched(_no_db):
    field = _Field("@dianeou38 Merci !")
    act = _action(field=field)

    act.reply_to_comment_in_thread("dianeou38", "Merci !")

    assert field.get_text() == "@dianeou38 Merci !"  # not rewritten


def test_an_unreadable_composer_is_not_overwritten(_no_db):
    """Better a reply we cannot verify than a correct one clobbered by a blind rewrite."""
    class _Unreadable(_Field):
        def get_text(self):
            raise RuntimeError("no text")

    field = _Unreadable("@dianeou38 Merci !")
    act = _action(field=field)

    act.reply_to_comment_in_thread("dianeou38", "Merci !")

    assert field._text == "@dianeou38 Merci !"


# ── Refusals ────────────────────────────────────────────────────────────────

def test_nothing_is_published_when_the_thread_is_not_open(_no_db):
    act = _action(comments_open=False)
    result = act.reply_to_comment_in_thread("dianeou38", "Merci !")
    assert result["success"] is False
    assert act.actions == [] and not _no_db


def test_an_absent_commenter_is_never_answered(_no_db):
    act = _action()
    result = act.reply_to_comment_in_thread("someone_else", "Merci !", max_scrolls=2)
    assert result["success"] is False
    assert act.device.taps == [] and act.actions == []


@pytest.mark.parametrize("username,text", [("", "Merci !"), ("dianeou38", ""), ("", "")])
def test_an_incomplete_request_is_refused_without_touching_the_screen(_no_db, username, text):
    act = _action()
    assert act.reply_to_comment_in_thread(username, text)["success"] is False
    assert act.device.taps == []


def test_a_reply_that_could_not_be_typed_is_not_recorded(_no_db):
    act = _action(typed_ok=False)
    result = act.reply_to_comment_in_thread("dianeou38", "Merci !")
    assert result["success"] is False
    assert act.actions == [] and not _no_db


def test_a_reply_that_could_not_be_sent_is_not_recorded(_no_db):
    """The text is in the box but never left the device — counting it would invent an action."""
    act = _action(sent_ok=False)
    result = act.reply_to_comment_in_thread("dianeou38", "Merci !")
    assert result["success"] is False
    assert act.actions == [] and not _no_db
