from taktik.core.social_media.tiktok.services.publish_screen_detector import (
    is_camera_creation_screen,
    is_gallery_picker_open,
    is_post_screen,
    is_video_edit_screen,
    wait_for_tiktok_home,
)


class FakeXpathResult:
    def __init__(self, matches: bool):
        self.matches = matches

    def wait(self, timeout: float = 0) -> bool:
        return self.matches


class FakeDumpDevice:
    def __init__(self, xml: str, matched_xpaths: set[str] | None = None):
        self.xml = xml
        self.matched_xpaths = matched_xpaths or set()

    def dump_hierarchy(self, compressed: bool = False) -> str:
        return self.xml

    def xpath(self, xpath: str) -> FakeXpathResult:
        return FakeXpathResult(xpath in self.matched_xpaths)


def test_is_gallery_picker_open_reads_xml_marker():
    device = FakeDumpDevice('<node resource-id="pkg:id/mub" />')

    assert is_gallery_picker_open(device)


def test_is_camera_creation_screen_reads_xml_markers():
    device = FakeDumpDevice('<node text="Add sound" /><node resource-id="pkg:id/r3r" />')

    assert is_camera_creation_screen(device)


def test_is_post_screen_reads_marker_or_lxml_selector():
    assert is_post_screen(FakeDumpDevice('<node resource-id="pkg:id/g19" />'))

    device = FakeDumpDevice(
        '<hierarchy><node class="android.widget.Button" content-desc="Post" /></hierarchy>'
    )
    assert is_post_screen(device)


def test_is_video_edit_screen_reads_xml_markers():
    device = FakeDumpDevice(
        '<node text="Annuler" /><node text="Enregistrer" /><node resource-id="pkg:id/xay" />'
    )

    assert is_video_edit_screen(device)


def test_wait_for_tiktok_home_returns_when_indicator_matches():
    matched = {'//*[contains(@resource-id, ":id/nc_")]'}
    device = FakeDumpDevice("<hierarchy />", matched_xpaths=matched)

    assert wait_for_tiktok_home(device, timeout=5, log=lambda _level, _msg: None)
