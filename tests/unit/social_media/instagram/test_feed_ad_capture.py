"""Harvesting the sponsored posts a feed run glides past.

The crawl has always recognised ads in order to skip them, and threw the recognition away.
This keeps it — but the collection is a SIDE EFFECT of a run, so the tests here are as much
about what it must never do (change the crawl, cost the run, inflate its own counter) as
about what it collects.
"""

import pytest
from PIL import Image
import numpy as np

from taktik.core.shared.vision.fingerprint import dhash, hamming_distance


def _image(seed, size=(400, 300)):
    rng = np.random.default_rng(seed)
    return Image.fromarray(rng.integers(0, 255, size[::-1], dtype=np.uint8))


# ─────────────────────────────────────────────────────────── fingerprint

def test_the_same_creative_re_encoded_keeps_its_fingerprint():
    """Two screenshots of one ad are never byte-identical — the phone re-encodes and the
    frame shifts. A cryptographic hash would count one creative as four."""
    original = _image(7)
    re_encoded = original.resize((200, 150)).resize((400, 300))
    assert hamming_distance(dhash(original), dhash(re_encoded)) <= 4


def test_two_different_creatives_are_far_apart():
    assert hamming_distance(dhash(_image(1)), dhash(_image(2))) > 10


def test_fingerprinting_never_raises_on_junk():
    """Fingerprinting a screenshot must not be able to break the run that took it."""
    assert dhash(None) is None
    assert hamming_distance(None, "abc") is None
    assert hamming_distance("zz", "zz") is None       # not hex


# ──────────────────────────────────────────────────── the crawl stays dumb

def test_the_crawl_reports_the_ad_while_it_is_still_on_screen():
    """The capture window is one instant: the ad is identified, the dump is fresh, and the
    next statement flicks it away. Calling back anywhere else captures the wrong screen."""
    import inspect
    from taktik.core.social_media.instagram.actions.atomic.scroll import feed_scroll

    source = inspect.getsource(feed_scroll.FeedScrollMixin.scroll_feed_to_next_post)
    before_flick = source.split("self._strong_flick")
    # the on_ad call must appear in the ad branch, ahead of the skipping flick
    ad_branch = source[source.index("if is_ad:"):]
    assert "on_ad(anchors)" in ad_branch.split("self._strong_flick")[0]
    assert len(before_flick) > 1


def test_a_failing_callback_cannot_break_the_crawl():
    """Collecting market intelligence is a side effect; it must never cost the run."""
    import inspect
    from taktik.core.social_media.instagram.actions.atomic.scroll import feed_scroll

    source = inspect.getsource(feed_scroll.FeedScrollMixin.scroll_feed_to_next_post)
    guarded = source[source.index("on_ad(anchors)"):]
    assert "except Exception" in guarded[:200]


def test_capture_is_off_by_default():
    """An untouched feed run must behave exactly as before — no screenshot, no callback."""
    from taktik.core.social_media.instagram.actions.business.common.workflow_defaults import (
        FEED_DEFAULTS,
    )
    assert FEED_DEFAULTS['capture_ads'] is False


# ────────────────────────────────────────────────────────── the capturer

class _Device:
    def __init__(self, image=None):
        self._image = image if image is not None else _image(3)
        self.shots = 0

    def screenshot_pil(self):
        self.shots += 1
        return self._image

    def get_screen_size(self):
        return (400, 300)


@pytest.fixture
def _recorded(monkeypatch):
    """Capture what would be written, without touching a database."""
    rows = []
    import taktik.core.database.instagram_feed_ads as mod

    class _Service:
        @staticmethod
        def record_sighting(**kwargs):
            rows.append(kwargs)
            return len(rows)

    monkeypatch.setattr(mod, 'InstagramFeedAdsService', _Service)
    return rows


def test_it_records_the_advertiser_and_a_fingerprint(_recorded):
    from taktik.core.social_media.instagram.actions.business.workflows.feed.ad_capture import (
        make_ad_capturer,
    )
    capture = make_ad_capturer(_Device(), account_id=42, read_text=False)
    capture({'ad_tops': [120], 'posts': [(100, 'cbd_brand')]})

    assert len(_recorded) == 1
    row = _recorded[0]
    assert row['advertiser'] == 'cbd_brand'
    assert row['account_id'] == 42
    assert row['creative_hash']
    assert row['screenshot']            # JPEG bytes


def test_the_same_ad_twice_yields_the_same_key(_recorded):
    """Dedup happens on this value: if it moved between two sightings of one creative, the
    corpus would count encounters as distinct ads and `times_seen` would mean nothing."""
    from taktik.core.social_media.instagram.actions.business.workflows.feed.ad_capture import (
        make_ad_capturer,
    )
    device = _Device()
    capture = make_ad_capturer(device, read_text=False)
    anchors = {'ad_tops': [120], 'posts': [(100, 'cbd_brand')]}
    capture(anchors)
    capture(anchors)

    assert _recorded[0]['creative_hash'] == _recorded[1]['creative_hash']


def test_a_broken_screenshot_records_nothing_and_raises_nothing(_recorded):
    from taktik.core.social_media.instagram.actions.business.workflows.feed.ad_capture import (
        make_ad_capturer,
    )

    class _Blind(_Device):
        def screenshot_pil(self):
            return None

    make_ad_capturer(_Blind(), read_text=False)({'ad_tops': [120], 'posts': []})
    assert _recorded == []


def test_an_ad_with_no_readable_advertiser_is_still_worth_recording(_recorded):
    """The creative and how often it comes back are the signal; the account name is a bonus."""
    from taktik.core.social_media.instagram.actions.business.workflows.feed.ad_capture import (
        make_ad_capturer,
    )
    make_ad_capturer(_Device(), read_text=False)({'ad_tops': [120], 'posts': []})

    assert len(_recorded) == 1
    assert _recorded[0]['advertiser'] is None


# ───────────────────────────────────────────────── the EN ad label selector

def test_the_english_ad_label_is_matched_exactly_not_by_containment():
    """`contains(@text, "Ad")` also matched "Add to story" — which sits in the feed's own
    story tray — so a normal English feed marked its first post as sponsored and skipped it.
    With capture on, it would have polluted the corpus as well."""
    etree = pytest.importorskip("lxml.etree")
    from taktik.core.social_media.instagram.ui.selectors import locales as ig_locales
    from taktik.core.social_media.instagram.ui.selectors.locales import en

    before = ig_locales.active_locale()
    try:
        ig_locales.set_active_locale('en')
        doc = etree.fromstring(
            '<hierarchy><node text="Add to story"/><node text="Adam Smith"/>'
            '<node text="Ads you might like"/><node text="Sponsored"/>'
            '<node text="Ad"/></hierarchy>'
        )
        matched = set()
        for selector in en.STRINGS["feed.sponsored_indicators"]:
            matched.update(n.get("text") for n in doc.xpath(selector))
        assert matched == {"Sponsored", "Ad"}
    finally:
        ig_locales.set_active_locale(before)
