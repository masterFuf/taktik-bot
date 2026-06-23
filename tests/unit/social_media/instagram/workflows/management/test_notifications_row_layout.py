"""Unit tests for follow-request row geometry helpers (pure)."""

from taktik.core.social_media.instagram.workflows.management.notifications.row_layout import (
    center,
    index_of_closest_row,
    parse_bounds,
    vertical_center,
)


def test_parse_bounds_ok():
    assert parse_bounds("[10,20][30,40]") == (10, 20, 30, 40)


def test_parse_bounds_invalid():
    assert parse_bounds("") is None
    assert parse_bounds("garbage") is None


def test_vertical_center_and_center():
    assert vertical_center((0, 20, 0, 40)) == 30.0
    assert center((10, 20, 30, 40)) == (20, 30)


def test_index_of_closest_row():
    # Confirm buttons at y=15, 35, 105; a username at y=31 belongs to the 2nd row.
    assert index_of_closest_row(31, [15, 35, 105]) == 1
    assert index_of_closest_row(110, [15, 35, 105]) == 2


def test_index_of_closest_row_empty():
    assert index_of_closest_row(50, []) is None
