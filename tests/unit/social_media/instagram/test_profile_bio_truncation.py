from taktik.core.social_media.instagram.actions.atomic.detection.profile_extraction import (
    ProfileExtractionMixin,
    _bio_text_looks_truncated,
)


class _Log:
    def debug(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


class _Device:
    def __init__(self, xml=""):
        self.xml = xml
        self.dump_calls = []
        self.clicks = []

    def get_xml_dump(self, **kwargs):
        self.dump_calls.append(kwargs)
        return self.xml

    def click_coordinates(self, x, y):
        self.clicks.append((x, y))


def _host(device):
    host = object.__new__(ProfileExtractionMixin)
    host.device = device
    host.logger = _Log()
    host._human_like_delay = lambda *_args, **_kwargs: None
    return host


def _profile_xml(bio):
    return (
        '<hierarchy><node resource-id="com.instagram.android:id/action_bar_title" '
        'text="target"/><node resource-id="com.instagram.android:id/'
        'profile_user_info_compose_view"><android.widget.TextView '
        f'text="{bio}" bounds="[120,300][960,520]"/>'
        '</node></hierarchy>'
    )


def test_dots_inside_user_bio_do_not_trigger_expensive_expansion():
    bio = "........\nActor FR/DE/EN\nDay dreamer\nStudent at actinglinestudio"

    assert _bio_text_looks_truncated(bio, ["more", "plus", "suite"]) is False


def test_trailing_ellipsis_without_accessible_expander_is_truncated():
    assert _bio_text_looks_truncated(
        "Long biography cut by Instagram…", ["more", "plus", "suite"]
    ) is True


def test_localized_expander_suffix_is_truncated():
    assert _bio_text_looks_truncated(
        "Biographie longue… plus", ["more", "plus", "suite"]
    ) is True
    assert _bio_text_looks_truncated(
        "Long biography... more", ["more", "plus", "suite"]
    ) is True


def test_enriched_profile_carries_bio_bounds_from_its_existing_dump():
    device = _Device(_profile_xml("Long biography... more"))

    data = _host(device).get_enriched_profile_data()

    assert data["bio_truncated"] is True
    assert data["_bio_region"] == (120, 300, 960, 520)
    assert device.dump_calls == [{}]


def test_expand_with_known_region_does_not_request_another_dump(monkeypatch):
    device = _Device()
    host = _host(device)
    match = type("Match", (), {"top": 410, "center": (875, 430)})()
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.atomic.detection."
        "profile_extraction.locate_text_on_screen",
        lambda *_args, **_kwargs: [match],
    )

    assert host.click_bio_more_button(region=(120, 300, 960, 520)) is True
    assert device.dump_calls == []
    assert device.clicks == [(875, 430)]


def test_direct_expand_requests_a_bounded_dump():
    device = _Device(_profile_xml("Long biography... more"))
    host = _host(device)

    # No screenshot implementation: expansion fails open after the bounded dump.
    assert host.click_bio_more_button() is False
    assert device.dump_calls == [{"timeout_seconds": 5.0}]
