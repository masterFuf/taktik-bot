"""The people of a comment thread are its authors, never someone a comment mentions (Instagram 447).

`read_visible_commenters` is the one reader of the people in a comment thread: the scraping of the
commenters, the interaction source of the same name (`list_sources.py`) and `post.read_commenters`
of the Lab take its rows and tap their element to open the profile. It knew one shape of author,
a Button with an empty description. From 442 on (447 included) the author is a TextView that repeats
its handle in its description, and the Button with an empty description is a @mention inside a
body. On a Pixel 6a in French (Lab bench, October 2026) the thread of a post read one person, the
one a comment mentioned, and on another post none. The like and the reply in the thread already
told the two shapes apart (`comments_thread._username_nodes`); the reader now asks the same rule.

The screens are real dumps, anonymized: the comment sheet of a 447 post in French, five authors and
a comment that mentions a sixth person (`ig447_fr_comment_sheet.xml`), and the 410 comment sheets
of the depot, whose authors are Buttons: their reading does not change.
"""

import pytest

from taktik.core.social_media.instagram.workflows.common.detection import read_visible_commenters
from unit.social_media.instagram.actions.atomic.interaction.sheet_phone import SheetPhone, capture

SHEET_447 = "ig447_fr_comment_sheet.xml"


def _rows(name):
    xml = capture(name)
    return read_visible_commenters(SheetPhone(xml, xml)), xml


def test_the_capture_holds_a_mention_shaped_as_an_older_author():
    """What the test stands on: the mentioned person is a Button with an empty description."""
    xml = capture(SHEET_447)
    assert 'text="@user_4" resource-id="" class="android.widget.Button"' in xml
    assert 'content-desc="user_3 a dit ...... @user_4"' in xml


def test_a_447_thread_reads_its_authors():
    rows, _xml = _rows(SHEET_447)

    assert [row["username"] for row in rows] == ["user_1", "user_2", "user_3", "user_5", "user_6", "user_7"]


def test_a_mention_is_never_read_as_an_author():
    rows, _xml = _rows(SHEET_447)

    assert "user_4" not in [row["username"] for row in rows]


def test_the_tap_of_an_author_lands_on_its_name():
    """The element a caller taps to open the profile is the author's name, not the avatar beside it:
    the avatar of an author with a story up opens the story (« Voir la story de ... »)."""
    rows, xml = _rows(SHEET_447)
    phone = SheetPhone(xml, xml)
    author = rows[0]
    left, top, right, bottom = author["element"].bounds
    x, y = author["element"].center()

    assert author["element"].attrib.get("content-desc", "").strip() == "user_1"
    assert left <= x <= right and top <= y <= bottom
    assert phone.gestures == []


#: What the reader gave on the 410 sheets before the 447 rule, Buttons with an empty description.
BASELINE_410 = {
    "ig410_en_comment_sheet.xml": ["name_8", "name_10", "user_2", "user_4", "name_12", "name_14"],
    "ig410_en_comment_sheet_expanded_keyboard_c57s.xml": ["user_1", "name_59", "user_2"],
    "ig410_en_comment_sheet_litho_bodies.xml": ["name_1", "name_2", "name_3"],
    "ig410_fr_comment_sheet.xml": ["user_1", "user_2", "user_3", "user_2", "name_7"],
    "ig410_fr_comment_sheet_from_grid.xml": ["user_1", "name_44", "user_9"],
}


@pytest.mark.parametrize("name", sorted(BASELINE_410))
def test_a_410_thread_is_read_as_before(name):
    rows, _xml = _rows(name)

    assert [row["username"] for row in rows] == BASELINE_410[name]
