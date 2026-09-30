"""Unit tests for database model compatibility exports."""

from taktik.core.database.models import Column, DatabaseQuery, DatabaseSession, InstagramProfile
from taktik.core.database.models.instagram_profile import InstagramProfile as OwnerInstagramProfile


def test_database_models_package_reexports_instagram_profile_owner():
    assert InstagramProfile is OwnerInstagramProfile
    assert Column("username") == ("username", "alice")
    assert DatabaseSession is not None
    assert DatabaseQuery is not None


def test_instagram_profile_keeps_legacy_alias_properties():
    profile = InstagramProfile(
        username="alice",
        followers_count=10,
        following_count=2,
        posts_count=3,
    )

    assert profile.followers == 10
    assert profile.following == 2
    assert profile.posts == 3

    profile.followers = 11
    profile.following = 4
    profile.posts = 5

    assert profile.followers_count == 11
    assert profile.following_count == 4
    assert profile.posts_count == 5
