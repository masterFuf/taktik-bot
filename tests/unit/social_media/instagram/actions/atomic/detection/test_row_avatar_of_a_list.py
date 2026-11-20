"""Each row of a follow list or a likers sheet is read with the bounds of its own picture.

A scrape that opens no profile sees an account only in its row: the picture there is the only one
it can keep (the Activity showed initials, 2026-10-29). The row's picture is the ImageView of
`follow_list_user_imageview` (a follow list) or `row_user_imageview` (a likers sheet), paired with
the username by height, on the same photo. The screens are real dumps, anonymized: Instagram 410
(English followers, French likers) and 447 (French followers, French likers). The expected picture
of a row is the ImageView found in that row's own container, not by the pairing under test.
"""

import pytest
from lxml import etree

from test_row_follow_state import _host
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
ROW_CONTAINERS = ("follow_list_container", "row_user_container_base")
AVATAR_IDS = ("follow_list_user_imageview", "row_user_imageview")
USERNAME_IDS = ("follow_list_username", "row_user_primary_name")


def _short(node) -> str:
    return node.get("resource-id", "").rsplit("/", 1)[-1]


def _bounds(text: str) -> tuple:
    return tuple(int(v) for v in text.replace("][", ",").strip("[]").split(","))


def _expected(xml: str) -> dict:
    """Username -> the bounds of the ImageView in its own row."""
    expected = {}
    for row in etree.fromstring(xml.encode("utf-8")).iter("node"):
        if _short(row) not in ROW_CONTAINERS:
            continue
        names = [n.get("text") for n in row.iter("node") if _short(n) in USERNAME_IDS and n.get("text")]
        avatars = [_bounds(n.get("bounds")) for n in row.iter("node")
                   if _short(n) in AVATAR_IDS and n.get("class") == "android.widget.ImageView"]
        if names and avatars:
            expected[names[0]] = avatars[0]
    return expected


@pytest.mark.parametrize("capture", [
    "ig410_en_followers_list.xml",
    "ig410_fr_likers_sheet.xml",
    "ig447_fr_own_followers_list.xml",
    "ig447_fr_likers_sheet_over_post_after_search.xml",
])
def test_each_row_is_read_with_the_picture_of_its_own_row(capture):
    xml = (FIXTURES / capture).read_text(encoding="utf-8")
    expected = _expected(xml)
    host, _phone = _host(xml)

    rows = host.get_visible_followers_with_elements()

    read = {row["username"]: row["avatar_bounds"] for row in rows if row["username"] in expected}
    assert expected and read == expected
