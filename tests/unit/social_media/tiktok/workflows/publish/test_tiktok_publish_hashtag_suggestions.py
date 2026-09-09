from taktik.core.social_media.tiktok.services.publish.hashtag_suggestions import (
    tap_hashtag_suggestion_from_dump,
)


class FakeDumpDevice:
    def __init__(self, xml: str):
        self.xml = xml
        self.clicks = []

    def dump_hierarchy(self, compressed: bool = False) -> str:
        return self.xml

    def click(self, x: int, y: int) -> None:
        self.clicks.append((x, y))


def test_tap_hashtag_suggestion_from_dump_clicks_expected_tag_first():
    device = FakeDumpDevice(
        '<hierarchy>'
        '<node class="android.widget.TextView" text="#generic" bounds="[20,520][160,560]" />'
        '<node class="android.widget.TextView" text="#paris" bounds="[20,600][160,640]" />'
        '</hierarchy>'
    )

    assert tap_hashtag_suggestion_from_dump(device, "paris", settle_delay=0)
    assert device.clicks == [(90, 620)]


def test_tap_hashtag_suggestion_from_dump_ignores_header_suggestions():
    device = FakeDumpDevice(
        '<hierarchy>'
        '<node class="android.widget.TextView" text="#header" bounds="[20,120][160,160]" />'
        '<node class="android.widget.TextView" text="#visible" bounds="[20,520][160,560]" />'
        '</hierarchy>'
    )

    assert tap_hashtag_suggestion_from_dump(device, settle_delay=0)
    assert device.clicks == [(90, 540)]


def test_tap_hashtag_suggestion_from_dump_returns_false_without_candidates():
    device = FakeDumpDevice(
        '<hierarchy>'
        '<node class="android.widget.TextView" text="not-a-tag" bounds="[20,520][160,560]" />'
        '</hierarchy>'
    )

    assert not tap_hashtag_suggestion_from_dump(device, settle_delay=0)
    assert device.clicks == []


def test_tap_hashtag_suggestion_from_4673_dump_prefers_exact_jt_text():
    device = FakeDumpDevice(
        '<hierarchy>'
        '<node resource-id="pkg:id/f15" class="android.widget.LinearLayout" clickable="true" bounds="[0,548][720,637]">'
        '<node resource-id="pkg:id/jt_" class="android.widget.TextView" text="#stickman" bounds="[28,576][155,609]" />'
        '</node>'
        '<node resource-id="pkg:id/f15" class="android.widget.LinearLayout" clickable="true" bounds="[0,637][720,726]">'
        '<node resource-id="pkg:id/jt_" class="android.widget.TextView" text="#stickmanwar" bounds="[28,665][197,698]" />'
        '</node>'
        '</hierarchy>'
    )

    assert tap_hashtag_suggestion_from_dump(device, "stickman", settle_delay=0)
    assert device.clicks == [(91, 592)]
