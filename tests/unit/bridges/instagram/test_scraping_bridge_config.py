"""The scraping config reading must forward the profile filters.

Device bug (2026-07-12): a profile with 0 posts was scraped, saved AND deep-qualified (paid AI)
even though the operator had set "Min posts = 1". The filter code itself was correct — it was
never fed: the reading (`scraping_config_from_payload`, the bridge's until it moved to the
core so the CLI reads the same) is a WHITELIST mapper and simply did not copy any of the
filter keys, so the workflow read them from an empty config and every filter evaluated to
"disabled". No min followers, no min posts, no skip-private: NONE of the scraping filters had
ever worked.

Also locks the upper-bound rule: the UI happily leaves 0 in a "max" field (seen on a real run:
"Max followers: 0"), which every operator reads as "no maximum". Forwarding it literally would
reject every profile with a single follower and scrape nothing.
"""

import pytest

from taktik.core.social_media.instagram.workflows.scraping.payload import (
    scraping_config_from_payload as build_scraping_config,
)


def _cfg(**over):
    base = {'type': 'target', 'targetUsernames': ['someone']}
    base.update(over)
    return build_scraping_config(base)


def test_min_posts_reaches_the_workflow():
    """The exact regression: minPosts=1 must not be dropped."""
    assert _cfg(minPosts=1)['minPosts'] == 1


def test_every_filter_key_is_forwarded():
    cfg = _cfg(
        minFollowers=10, maxFollowers=50000,
        minFollowing=50, maxFollowing=7500,
        minPosts=3,
        requireProfilePicture=True, skipPrivateProfiles=False,
    )
    assert cfg['minFollowers'] == 10
    assert cfg['maxFollowers'] == 50000
    assert cfg['minFollowing'] == 50
    assert cfg['maxFollowing'] == 7500
    assert cfg['minPosts'] == 3
    assert cfg['requireProfilePicture'] is True
    assert cfg['skipPrivateProfiles'] is False


def test_absent_filter_stays_disabled():
    """The front sends null for an empty field — the key must not appear at all."""
    cfg = _cfg(minPosts=None, minFollowers=None)
    assert 'minPosts' not in cfg
    assert 'minFollowers' not in cfg


def test_zero_lower_bound_is_kept_literally():
    """0 is a meaningful lower bound (and harmless) — it must not be swallowed by a truthy test."""
    assert _cfg(minPosts=0)['minPosts'] == 0


def test_zero_upper_bound_means_no_limit_not_zero_followers():
    """The guard that prevents a far worse bug: 'Max followers: 0' must not scrape nothing."""
    cfg = _cfg(maxFollowers=0, maxFollowing=0)
    assert 'maxFollowers' not in cfg
    assert 'maxFollowing' not in cfg


def test_skip_private_defaults_to_true():
    assert _cfg()['skipPrivateProfiles'] is True
    assert _cfg()['requireProfilePicture'] is False


def test_filters_do_not_disturb_the_rest_of_the_config():
    cfg = _cfg(minPosts=1, maxProfiles=250, enrichProfiles=True, deepQualify=True)
    assert cfg['max_profiles'] == 250
    assert cfg['enrich_profiles'] is True
    assert cfg['deep_qualify'] is True
    assert cfg['type'] == 'target'


def test_location_is_opt_in_and_off_by_default():
    """Enriched scraping must NOT drag in the slow About-account navigation unless asked.

    The location screen (country/city) is a separate, slower page whose back-press can overshoot;
    the profile visit already yields stats/bio/filters without it. The default flipping to True
    would silently slow down every enriched scrape and reintroduce that navigation bug."""
    assert _cfg(enrichProfiles=True)['fetchLocation'] is False
    assert _cfg(enrichProfiles=True, fetchLocation=True)['fetchLocation'] is True
