from taktik.core.social_media.tiktok.services.publish_upload_picker import (
    tap_upload_button_from_dump,
)


class FakeDumpDevice:
    def __init__(self, xml: str):
        self.xml = xml
        self.clicks = []

    def dump_hierarchy(self, compressed: bool = False) -> str:
        return self.xml

    def click(self, x: int, y: int) -> None:
        self.clicks.append((x, y))


def test_tap_upload_button_from_dump_clicks_visible_candidate_bounds():
    device = FakeDumpDevice(
        '<hierarchy>'
        '<node resource-id="com.zhiliaoapp.musically:id/ce9" bounds="[409,945][529,1065]" clickable="true" />'
        '</hierarchy>'
    )

    assert tap_upload_button_from_dump(device)
    assert device.clicks == [(469, 1005)]


def test_tap_upload_button_from_dump_prefers_clickable_candidate():
    device = FakeDumpDevice(
        '<hierarchy>'
        '<node resource-id="pkg:id/ymg" bounds="[10,10][60,60]" clickable="false" />'
        '<node resource-id="pkg:id/ce9" bounds="[100,100][180,180]" clickable="true" />'
        '</hierarchy>'
    )

    assert tap_upload_button_from_dump(device)
    assert device.clicks == [(140, 140)]


def test_tap_upload_button_from_dump_ignores_hidden_disabled_or_tiny_nodes():
    device = FakeDumpDevice(
        '<hierarchy>'
        '<node resource-id="pkg:id/ymg" bounds="[10,10][15,15]" clickable="true" />'
        '<node resource-id="pkg:id/ce9" bounds="[100,100][180,180]" clickable="true" visible-to-user="false" />'
        '<node resource-id="pkg:id/cl2" bounds="[200,200][280,280]" clickable="true" enabled="false" />'
        '</hierarchy>'
    )

    assert not tap_upload_button_from_dump(device)
    assert device.clicks == []
