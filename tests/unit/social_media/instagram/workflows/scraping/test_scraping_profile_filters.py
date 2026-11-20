"""Profile filters of the scraping workflow — the decision itself.

The companion of tests/unit/bridges/instagram/test_scraping_bridge_config.py: that one proves the
filters REACH the workflow, this one proves the workflow DECIDES correctly once it has them.

Device bug (2026-07-12): "@sample_profile, 0 posts" was scraped with Min posts = 1. The filter
below always rejected it — it just never received minPosts (see the bridge test). The 0-post case
is kept here anyway: it is the exact profile the operator saw, and a future refactor introducing a
truthy test (`if posts_count and posts_count < min_posts`) would silently let 0 through again.
"""

import pytest

from taktik.core.social_media.instagram.workflows.scraping.list_scraping import ScrapingListMixin


class _Workflow(ScrapingListMixin):
    """Bare host for the mixin — the filter reads nothing but self.config."""

    def __init__(self, config):
        self.config = config


def _profile(**over):
    base = {
        'username': 'someone',
        'followers_count': 500,
        'following_count': 300,
        'posts_count': 10,
        'is_private': False,
        'profile_pic_base64': 'xxx',
    }
    base.update(over)
    return base


def test_zero_posts_is_rejected_when_min_posts_is_one():
    """The exact profile from the device report."""
    wf = _Workflow({'minPosts': 1})
    assert wf._get_profile_filter_reason(_profile(posts_count=0)) == 'few_posts'


def test_no_filters_accepts_everything():
    wf = _Workflow({'skipPrivateProfiles': False})
    assert wf._get_profile_filter_reason(_profile(posts_count=0, followers_count=0)) is None


@pytest.mark.parametrize('config,profile,expected', [
    ({'minFollowers': 100}, {'followers_count': 12}, 'low_followers'),
    ({'maxFollowers': 1000}, {'followers_count': 5000}, 'high_followers'),
    ({'minFollowing': 50}, {'following_count': 10}, 'low_following'),
    ({'maxFollowing': 7500}, {'following_count': 9000}, 'high_following'),
    ({'requireProfilePicture': True}, {'profile_pic_base64': None}, 'no_profile_picture'),
    ({}, {'is_private': True}, 'private'),  # skipPrivateProfiles defaults to True
])
def test_each_filter_rejects_what_it_should(config, profile, expected):
    wf = _Workflow(config)
    assert wf._get_profile_filter_reason(_profile(**profile)) == expected


def test_profile_within_all_bounds_passes():
    wf = _Workflow({
        'minFollowers': 10, 'maxFollowers': 50000,
        'minFollowing': 50, 'maxFollowing': 7500,
        'minPosts': 1, 'requireProfilePicture': True, 'skipPrivateProfiles': True,
    })
    assert wf._get_profile_filter_reason(_profile()) is None


def test_has_profile_filters_detects_the_operator_intent():
    """Drives the enrichment-failure skip: an unverifiable profile must not be saved+AI-qualified
    when filters were requested, but nothing changes when none were."""
    assert _Workflow({'minPosts': 1})._has_profile_filters() is True
    assert _Workflow({'requireProfilePicture': True})._has_profile_filters() is True
    assert _Workflow({'skipPrivateProfiles': True})._has_profile_filters() is True
    # Everything off: no filter at all.
    assert _Workflow({'skipPrivateProfiles': False})._has_profile_filters() is False


@pytest.mark.parametrize('config,unread,expected', [
    ({'minFollowers': 100}, 'followers_count', 'followers_count_unreadable'),
    ({'maxFollowers': 1000}, 'followers_count', 'followers_count_unreadable'),
    ({'minFollowing': 50}, 'following_count', 'following_count_unreadable'),
    ({'minPosts': 1}, 'posts_count', 'posts_count_unreadable'),
])
def test_a_bound_on_a_counter_not_read_refuses_it_as_unreadable(config, unread, expected):
    wf = _Workflow(config)
    assert wf._get_profile_filter_reason(_profile(**{unread: None})) == expected


def test_a_counter_not_read_without_a_bound_on_it_passes():
    wf = _Workflow({'minFollowers': 100, 'minFollowing': 0})
    assert wf._get_profile_filter_reason(_profile(posts_count=None, following_count=None)) is None
