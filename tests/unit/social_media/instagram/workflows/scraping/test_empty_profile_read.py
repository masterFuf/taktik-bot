"""A profile page that gave nothing must not be qualified.

`get_complete_profile_info` returns a populated dict even when the screen was never there to be
read: every field comes back at its default, so the run used to carry on and qualify the profile
from its username alone. Measured on the 2026-08-27 run: 36 profiles saved with 0 followers,
0 posts, no name and no bio, every one of them handed an invented niche at an average confidence
of 0.95.

The guard is unanimous on purpose — these lock both halves of that: what it catches, and the real
accounts it must never catch.
"""

from taktik.core.social_media.instagram.workflows.scraping.list_scraping import _read_nothing


class TestReadNothing:
    def test_a_page_that_was_never_drawn(self):
        # The exact shape of the 36 profiles the run damaged.
        assert _read_nothing({
            'followers_count': 0, 'following_count': 0, 'posts_count': 0,
            'full_name': '', 'biography': '',
        }) is True

    def test_missing_keys_read_as_nothing(self):
        assert _read_nothing({}) is True

    def test_none_values_read_as_nothing(self):
        assert _read_nothing({
            'followers_count': None, 'following_count': None, 'posts_count': None,
            'full_name': None, 'biography': None,
        }) is True

    def test_whitespace_is_not_content(self):
        assert _read_nothing({
            'followers_count': 0, 'following_count': 0, 'posts_count': 0,
            'full_name': '   ', 'biography': '\n',
        }) is True


class TestRealAccountsSurvive:
    """Anything short of unanimity is a real account — the guard must let it through."""

    def test_private_account_still_reports_counters(self):
        assert _read_nothing({
            'followers_count': 412, 'following_count': 300, 'posts_count': 12,
            'full_name': 'Marie', 'biography': '', 'is_private': True,
        }) is False

    def test_brand_new_account_with_a_single_follow(self):
        assert _read_nothing({
            'followers_count': 0, 'following_count': 8, 'posts_count': 0,
            'full_name': '', 'biography': '',
        }) is False

    def test_empty_account_that_at_least_has_a_name(self):
        assert _read_nothing({
            'followers_count': 0, 'following_count': 0, 'posts_count': 0,
            'full_name': 'Jean Dupont', 'biography': '',
        }) is False

    def test_empty_account_that_at_least_has_a_bio(self):
        assert _read_nothing({
            'followers_count': 0, 'following_count': 0, 'posts_count': 0,
            'full_name': '', 'biography': 'Photographe',
        }) is False
