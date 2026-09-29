"""`collect_post` (the Lab's `tt.video.collect_post`) reads the video's identity before the share sheet.

The author comes from the detector that already answers it (`VideoDetector.get_video_author`). Its
lazy import aimed at `actions/detection/video_detector`, which does not exist (the detector lives
under `actions/atomic/detection/`): `collect_post` raised before any read, and the Lab action failed.

The screen is a real capture: a For You video, TikTok 43.1.4 in French (Pixel 3a), anonymized,
read by uiautomator2's own `XPathEntry`. The share sheet and the clipboard are not in it: the link
is handed in, the identity and the key are read.
"""

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

from taktik.core.database.tiktok_post_identity import tiktok_post_key
from taktik.core.social_media.tiktok.actions.atomic.interaction.post_link_actions import PostLinkActions
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from unit.paths import CORE

PKG = "com.zhiliaoapp.musically:id/"
VIDEO = (CORE / "tests/unit/social_media/tiktok/fixtures/tt4314_fr_for_you_video.xml").read_text(encoding="utf-8")
LINK = "https://vm.tiktok.com/ZNexample/"


class _Phone:
    """Shows the capture; the xpath queries are uiautomator2's."""

    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def window_size(self):
        return 1080, 2400


def _text(xml, rid):
    """What a node of the capture says, read without the production readers."""
    return etree.fromstring(xml.encode("utf-8")).xpath(f'//node[@resource-id="{PKG}{rid}"]')[0].get("text")


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def test_collect_post_reads_the_identity_of_the_video_then_keys_it(monkeypatch):
    actions = PostLinkActions(_Phone(VIDEO))
    monkeypatch.setattr(actions, "copy_post_link", lambda **_: LINK)

    collected = actions.collect_post()

    author, caption = _text(VIDEO, "title"), _text(VIDEO, "desc")
    assert collected == {
        "author": author,
        "posted_at_label": "",  # the For You feed renders no post date
        "caption": caption,
        "post_url": LINK,
        "post_key": tiktok_post_key(author, "", caption),
    }
