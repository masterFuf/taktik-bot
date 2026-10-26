"""The thread's comment reader reads the bodies Instagram writes on the screen (442 and 447).

`read_visible_comments` is the one reader of a comment thread: `comment.read_thread` of the Lab, the
context of an AI reply in the thread (`services/comment/thread_context.py`) and the in-thread pass of
Post URL (`post_url/in_thread.py`) take its records. It read the bodies only from the Litho dump of
`dumpsys activity top`, where Instagram 410 renders them. From 442 on, a body is a node of its row
that spells « <author> a dit <text> » (« said » in English), and the Litho dump holds none: on a
Pixel 6a in French (Instagram 447, Lab bench of October 2026) the thread showed one comment and the
reader gave none (« 0 comment(s) — none readable »). The persona reader already read those rows
(`read_comment_texts`), the thread's reader did not.

The screen is a real dump, anonymized: the comment sheet of a 447 post, in French, five comments
(`ig447_fr_comment_sheet.xml`). The Litho dump is what the phone gave on that build: nothing the
parser reads. The 410 thread, bodies in Litho only, is held by the tests of the persona reader
(`test_persona_reads_the_litho_comment_bodies.py`).
"""

import pytest

from taktik.core.shared.device.facade import BaseDeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.instagram.workflows.common import comment_reading
from unit.paths import CORE

SHEET = (CORE / "tests/unit/social_media/instagram/fixtures/ig447_fr_comment_sheet.xml").read_text(encoding="utf-8")


class _Phone:
    """uiautomator2 as the reader touches it: one dump of the screen."""

    serial = "PIXEL-6A"

    def __init__(self, xml):
        self.xml = xml

    def dump_hierarchy(self, *_a, **_k):
        return self.xml


class _NoLithoBodies:
    """`dumpsys activity top` on 447: an answer, without a single body in it."""

    returncode = 0
    stdout = "TASK com.instagram.android id=1\n  ACTIVITY com.instagram.android/.activity.MainTabActivity\n"
    stderr = ""


@pytest.fixture(autouse=True)
def _french(monkeypatch):
    before = active_locale()
    set_active_locale("fr")
    monkeypatch.setattr(comment_reading, "run_adb_shell_process", lambda *_a, **_k: _NoLithoBodies())
    yield
    set_active_locale(before)


def _read():
    return comment_reading.read_visible_comments(BaseDeviceFacade(_Phone(SHEET)), device_id="PIXEL-6A")


def test_the_capture_spells_its_bodies_on_the_screen():
    """What the test stands on: the rows say « <author> a dit <text> »."""
    assert SHEET.count(' a dit ') >= 5


def test_a_447_thread_is_read_from_its_rows():
    comments = _read()

    assert [c["username"] for c in comments] == ["user_1", "user_2", "user_3", "user_5", "user_6"]
    assert comments[0]["text"] == "name_2 ❤️"
    assert all(not c["text"].startswith(("user_", "a dit")) for c in comments)


def test_a_body_that_opens_with_a_mention_is_a_reply_to_that_person():
    by_author = {c["username"]: c for c in _read()}

    assert by_author["user_1"]["is_reply"] is False
    assert by_author["user_3"]["parent_username"] is None  # the mention is not at the start
