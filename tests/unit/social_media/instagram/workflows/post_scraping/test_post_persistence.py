from taktik.core.social_media.instagram.workflows.post_scraping.post_persistence import PostPersistenceMixin
from taktik.core.social_media.instagram.workflows.post_scraping.post_scraping_models import ScrapedProfile


class _FakeDb:
    def __init__(self):
        self.saved_profiles = []

    def save_profile(self, profile_data):
        self.saved_profiles.append(profile_data)
        return {"profile_id": len(self.saved_profiles), "created": True}


class _FakeLogger:
    def __init__(self):
        self.errors = []

    def error(self, message):
        self.errors.append(message)


class _Workflow(PostPersistenceMixin):
    def __init__(self):
        self.db = _FakeDb()
        self.logger = _FakeLogger()
        self.enriched_profiles = []


def test_save_to_database_delegates_profile_persistence():
    workflow = _Workflow()
    workflow.enriched_profiles = [
        ScrapedProfile(
            username="creator_one",
            source_type="commenter",
            source_post_url="https://instagram.test/p/1",
            bio="Bio one",
            website="https://example.com",
            followers_count=1200,
            following_count=150,
            posts_count=42,
            is_private=False,
            is_verified=True,
            is_business=True,
            category="Creator",
        ),
        ScrapedProfile(
            username="creator_two",
            source_type="liker",
            source_post_url="https://instagram.test/p/1",
            bio=None,
            website="",
            followers_count=85,
            following_count=33,
            posts_count=9,
            is_private=True,
            is_verified=False,
            is_business=False,
            category=None,
        ),
    ]

    workflow._save_to_database()

    assert workflow.logger.errors == []
    assert workflow.db.saved_profiles == [
        {
            "username": "creator_one",
            "biography": "Bio one",
            "followers_count": 1200,
            "following_count": 150,
            "posts_count": 42,
            "is_private": False,
            "is_verified": True,
            "is_business": True,
            "business_category": "Creator",
            "website": "https://example.com",
        },
        {
            "username": "creator_two",
            "biography": "",
            "followers_count": 85,
            "following_count": 33,
            "posts_count": 9,
            "is_private": True,
            "is_verified": False,
            "is_business": False,
            "business_category": None,
            "website": None,
        },
    ]
