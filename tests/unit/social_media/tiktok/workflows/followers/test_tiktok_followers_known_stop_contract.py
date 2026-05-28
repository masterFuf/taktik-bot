from taktik.core.social_media.tiktok.actions.business.workflows.followers.models import (
    FollowersConfig,
    FollowersStats,
)


def test_followers_config_has_known_username_stop_default():
    config = FollowersConfig()

    assert config.max_consecutive_known_usernames == 150


def test_followers_stats_exports_known_username_fields():
    stats = FollowersStats(
        known_usernames_seen=12,
        new_usernames_seen=3,
        consecutive_known_usernames=4,
    )

    exported = stats.to_dict()

    assert exported["known_usernames_seen"] == 12
    assert exported["new_usernames_seen"] == 3
    assert exported["consecutive_known_usernames"] == 4
