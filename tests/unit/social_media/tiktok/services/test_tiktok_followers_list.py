from taktik.core.social_media.tiktok.services.followers.listing import (
    find_follower_rows,
    follower_username_tap_point,
    tap_follower_username,
    vertical_bounds_overlap,
)
from taktik.core.social_media.tiktok.ui.selectors import FOLLOWERS_SELECTORS


class _FakeElement:
    def __init__(self, *, text="", bounds=None):
        self.text = text
        self.info = {"bounds": bounds or {}}


class _FakeXPath:
    def __init__(self, elements):
        self._elements = elements

    def all(self):
        return self._elements


class _FakeDevice:
    def __init__(self, elements_by_selector=None):
        self.elements_by_selector = elements_by_selector or {}
        self.selectors = []
        self.clicks = []

    def xpath(self, selector):
        self.selectors.append(selector)
        return _FakeXPath(self.elements_by_selector.get(selector, []))

    def click(self, x, y):
        self.clicks.append((x, y))


def test_vertical_bounds_overlap_detects_same_row():
    assert vertical_bounds_overlap({"top": 100, "bottom": 160}, {"top": 120, "bottom": 180})
    assert not vertical_bounds_overlap({"top": 10, "bottom": 40}, {"top": 50, "bottom": 80})


def test_find_follower_rows_matches_usernames_by_vertical_bounds():
    button_selector = FOLLOWERS_SELECTORS.follower_any_button[0]
    username_selector = FOLLOWERS_SELECTORS.follower_username[0]
    device = _FakeDevice(
        {
            button_selector: [
                _FakeElement(text="Follow", bounds={"top": 100, "bottom": 150}),
                _FakeElement(text="Friends", bounds={"top": 200, "bottom": 250}),
            ],
            username_selector: [
                _FakeElement(text="creator_one", bounds={"top": 105, "bottom": 130}),
                _FakeElement(text="creator_two", bounds={"top": 205, "bottom": 230}),
            ],
        }
    )

    rows = find_follower_rows(device)

    assert [row["username"] for row in rows] == ["creator_one", "creator_two"]
    assert [row["status"] for row in rows] == ["Follow", "Friends"]


def test_follower_username_tap_point_uses_username_area_x_and_row_center_y():
    assert follower_username_tap_point({"top": 100, "bottom": 160}) == (280, 130)


def test_tap_follower_username_clicks_calculated_point(monkeypatch):
    monkeypatch.setattr(
        "taktik.core.social_media.tiktok.services.followers.listing.time.sleep",
        lambda _seconds: None,
    )
    device = _FakeDevice()

    tapped = tap_follower_username(
        device,
        {"bounds": {"top": 100, "bottom": 160}, "username": "creator"},
    )

    assert tapped
    assert device.clicks == [(280, 130)]
