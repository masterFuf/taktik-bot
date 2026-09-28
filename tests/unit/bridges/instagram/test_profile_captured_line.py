"""A profile read goes out as what was read: a counter or a flag not read is left out, not zero.

`send_profile_captured` filled every key its profile data did not hold with 0 or false:
`follower_count: 0`, `following_count: 0`, `media_count: 0`, `is_private: false`,
`is_verified: false`. A profile not read then passed for a public profile with 0 followers. The
list scraping sends one for every row it keeps; without the profile opened (no enrichment, or a
tap that did not open it), its data is the row alone (`list_scraping.py`), and the scraping panel
showed "0 followers" for each.

The app's readers take each key as optional (`handleBotMessages`, `useAgentEvents`,
`ScrapingBridgeStreamService`, the contract's `profile_captured`: every field but `username`
optional), and the unfollow's line already carries no counter (its picture only).
"""

import pytest

from bridges.instagram.runtime import ipc_scraping_events

COUNTERS_AND_FLAGS = ("follower_count", "following_count", "media_count", "is_private", "is_verified")


@pytest.fixture
def lines(monkeypatch):
    sent = []

    class _Ipc:
        @staticmethod
        def send(line_type, **fields):
            sent.append({"type": line_type, **fields})

    monkeypatch.setattr(ipc_scraping_events, "_ipc", _Ipc)
    return sent


def test_a_row_the_scraping_did_not_open_has_no_counter(lines):
    """The data of a list row kept without its profile opened (`list_scraping.py`)."""
    row = {"username": "user_1", "source_type": "followers", "source_name": "user_2",
           "scraped_at": "2026-09-28T07:21:21"}

    ipc_scraping_events.send_profile_captured("user_1", row)

    assert lines == [{"type": "profile_captured", "username": "user_1"}]


def test_a_counter_that_could_not_be_read_is_left_out(lines):
    """The profile was opened, its followers not read (None), the rest read."""
    profile = {"username": "user_1", "full_name": "name_1", "followers_count": None, "following_count": 76,
               "posts_count": 25, "is_private": False, "is_verified": False, "biography": ""}

    ipc_scraping_events.send_profile_captured("user_1", profile, profile_pic_base64="data:image/jpeg;base64,AAAA")

    assert lines == [{"type": "profile_captured", "username": "user_1", "full_name": "name_1",
                      "following_count": 76, "media_count": 25, "is_private": False,
                      "is_verified": False, "biography": "", "profile_pic_url": "data:image/jpeg;base64,AAAA"}]


def test_a_profile_read_whole_goes_out_whole(lines):
    profile = {"username": "user_1", "full_name": "name_1", "followers_count": 209, "following_count": 76,
               "posts_count": 25, "is_private": True, "is_verified": True, "biography": "bio_1"}

    ipc_scraping_events.send_profile_captured("user_1", profile)

    assert lines == [{"type": "profile_captured", "username": "user_1", "full_name": "name_1",
                      "follower_count": 209, "following_count": 76, "media_count": 25,
                      "is_private": True, "is_verified": True, "biography": "bio_1"}]


def test_a_picture_alone_is_a_picture_alone(lines):
    """The unfollow's line: the profile read for its picture, no data."""
    ipc_scraping_events.send_profile_captured("user_1", profile_pic_base64="data:image/jpeg;base64,AAAA")

    assert lines == [{"type": "profile_captured", "username": "user_1",
                      "profile_pic_url": "data:image/jpeg;base64,AAAA"}]
    assert not set(COUNTERS_AND_FLAGS) & set(lines[0])
