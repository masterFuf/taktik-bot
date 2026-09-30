"""Answering a comment must land UNDER that comment.

Instagram threads a reply by the "@username " mention it prefills when the row's own Reply
affordance is tapped. Lose that mention and the reply silently becomes an ordinary top-level
comment addressed to nobody — published, counted, and wrong.

The thread is real: the comments sheet of a feed post, Instagram 410 in French (Pixel 3a; the
Lab filed the run under the launcher's version), anonymized, four comments on screen, each with its
own "Répondre" button.

On the comments sheet of a post opened from a grid ("Posts" in the action bar, Instagram
410.0.0.53.71 in English, Pixel 3, anonymized), the reply lands under its comment: the title
is not taken for an author (see the last test).
"""

import types

import pytest

from taktik.core.shared.device.snapshot import ScreenSnapshot
from taktik.core.social_media.instagram.services.comment.action import CommentAction
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
THREAD = (FIXTURES / "ig410_fr_comment_sheet.xml").read_text(encoding="utf-8")
#: The third comment of the sheet: its author, and the "Répondre" button of its own row.
COMMENTER = "user_3"
REPLY = (179, 887, 375, 973)
#: The sheet of a post opened from a grid, and one of its commenters with that row's Reply.
POSTS_THREAD = (FIXTURES / "ig410_en_comment_sheet.xml").read_text(encoding="utf-8")
POSTS_COMMENTER = "user_2"
POSTS_REPLY = (179, 1073, 310, 1159)


class _Field:
    """The comment composer, as uiautomator2 exposes it."""

    def __init__(self, text=""):
        self.exists = True
        self._text = text

    def get_text(self):
        return self._text

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

    def snapshot(self):
        # The facade's screen photo: one dump.
        return ScreenSnapshot(self.dump_hierarchy())

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
    act.device = _Device(xml, field if field is not None else _Field("@" + COMMENTER + " "), tap_ok=tap_ok)
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
    act._ensure_taktik_keyboard = lambda: True
    act._close_comment_popup = lambda: True
    act._type_comment = lambda _text, mention="": typed_ok
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
        "taktik.core.social_media.instagram.services.comment.action"
        ".InstagramPostedComments.record",
        staticmethod(lambda **kw: _record(**kw)),
    )
    return written


# ── The happy path ──────────────────────────────────────────────────────────

def test_a_reply_taps_the_rows_own_reply_button(_no_db):
    act = _action()

    result = act.reply_to_comment_in_thread(COMMENTER, "Merci pour ce retour !")

    assert result["success"] is True
    assert act.device.taps == [REPLY]  # this commenter's Reply, not a neighbour's


def test_the_reply_is_typed_and_checked_after_its_mention(_no_db):
    """The field must read "@" + COMMENTER + " Merci !" before the send, not just "Merci !"."""
    act = _action()
    mentions = []
    act._type_comment = lambda _text, mention="": mentions.append(mention) or True

    act.reply_to_comment_in_thread(COMMENTER, "Merci !")

    assert mentions == ["@" + COMMENTER + " "]


def test_a_reply_is_stored_as_a_reply_and_keeps_who_it_answers(_no_db):
    act = _action()

    act.reply_to_comment_in_thread(COMMENTER, "Merci !", reply_to_text="Super post")

    assert _no_db["kind"] == "reply"
    assert _no_db["target_username"] == COMMENTER   # the COMMENTER, not the post author
    assert _no_db["reply_to_username"] == COMMENTER
    assert _no_db["reply_to_text"] == "Super post"
    assert _no_db["comment_text"] == "Merci !"


def test_a_reply_is_ledgered_as_a_comment_with_its_text(_no_db):
    """A reply IS a published text: it consumes the comment budget and shows in the drill-down."""
    act = _action()
    act.reply_to_comment_in_thread(COMMENTER, "Merci !")
    assert act.actions == [(COMMENTER, "COMMENT", "Merci !")]


# ── The mention is the thread link ──────────────────────────────────────────
#
# A reply's typing is checked against its mention (`_type_comment(..., mention=...)`): the field
# without it is emptied and the mention typed with the reply, by the keyboard, nothing rewritten
# afterwards (`test_text_is_never_pasted.py`, a reply that lost its mention).


# ── Refusals ────────────────────────────────────────────────────────────────

def test_nothing_is_published_when_the_thread_is_not_open(_no_db):
    act = _action(comments_open=False)
    result = act.reply_to_comment_in_thread(COMMENTER, "Merci !")
    assert result["success"] is False
    assert act.actions == [] and not _no_db


def test_an_absent_commenter_is_never_answered(_no_db):
    act = _action()
    result = act.reply_to_comment_in_thread("someone_else", "Merci !", max_scrolls=2)
    assert result["success"] is False
    assert act.device.taps == [] and act.actions == []


@pytest.mark.parametrize("username,text", [("", "Merci !"), (COMMENTER, ""), ("", "")])
def test_an_incomplete_request_is_refused_without_touching_the_screen(_no_db, username, text):
    act = _action()
    assert act.reply_to_comment_in_thread(username, text)["success"] is False
    assert act.device.taps == []


def test_a_reply_that_could_not_be_typed_is_not_recorded(_no_db):
    act = _action(typed_ok=False)
    result = act.reply_to_comment_in_thread(COMMENTER, "Merci !")
    assert result["success"] is False
    assert act.actions == [] and not _no_db


def test_a_reply_that_could_not_be_sent_is_not_recorded(_no_db):
    """The text is in the box but never left the device — counting it would invent an action."""
    act = _action(sent_ok=False)
    result = act.reply_to_comment_in_thread(COMMENTER, "Merci !")
    assert result["success"] is False
    assert act.actions == [] and not _no_db


def test_a_reply_lands_under_its_comment_on_a_post_opened_from_a_grid(_no_db):
    act = _action(xml=POSTS_THREAD, field=_Field("@" + POSTS_COMMENTER + " "))

    result = act.reply_to_comment_in_thread(POSTS_COMMENTER, "Merci !", max_scrolls=1)

    assert result["success"] is True
    assert act.device.taps == [POSTS_REPLY]
