"""A scraped profile writes what was read: a key not read stays absent, down to the base.

The list scrape filled every key its profile visit did not return with a default
(`enriched_data.get('followers_count', 0)`, `''` for the About fields), and both saves of the
scraping workflow did the same for the row they write (`profile.get('followers_count', 0)`,
`is_private` false, an empty biography and name). The profile repository leaves a column alone
only for a key that is absent or None: a 0, a false or an empty string overwrites it. So a row kept
without its profile opened, or a visit that did not read a counter, wrote 0 followers, a public
account and an empty bio over a profile the base already knew.

Same rule as `send_profile_captured` (lot `correctifs`): a key not read (absent, or None) is left
out, never sent as 0, false or empty. The base is a real one (throwaway file), the profile visit
answers with the keys `get_complete_profile_info` returns.
"""

import pytest
from loguru import logger

from taktik.core.social_media.instagram.workflows.scraping.list_scraping import ScrapingListMixin
from taktik.core.social_media.instagram.workflows.scraping.persistence import ScrapingPersistenceMixin

KNOWN = {
    "followers_count": 1234, "following_count": 56, "posts_count": 78,
    "is_private": True, "is_verified": True, "biography": "bio_1", "full_name": "name_1",
    "business_category": "cat_1", "website": "site_1",
    "date_joined": "janvier 2019", "account_based_in": "France",
}


def _row(username="user_1"):
    """A list row kept as the scrape builds it, before any visit."""
    return {"username": username, "source_type": "FOLLOWERS", "source_name": "user_2",
            "scraped_at": "2026-09-28T03:00:00"}


class _Visit:
    """The profile visit: answers with what `get_complete_profile_info` returned."""

    def __init__(self, answer):
        self.answer = answer

    def get_complete_profile_info(self, **_kwargs):
        return dict(self.answer)


class _Scrape(ScrapingListMixin, ScrapingPersistenceMixin):
    def __init__(self, db, visit_answer=None):
        self.local_db = db
        self.config = {"skipPrivateProfiles": False}
        self.logger = logger
        self._save_immediately = True
        self.scraping_session_id = None
        self.scraped_profiles = []
        self.profile_manager = _Visit(visit_answer or {})


@pytest.fixture
def known(db):
    db.save_profile({"username": "user_1", **KNOWN})
    return db


def _stored(db, username="user_1"):
    profile = db.get_profile_by_username(username)
    return {key: profile.get(key) for key in KNOWN}


def test_a_row_kept_without_its_profile_leaves_the_known_profile_as_it_was(known):
    _Scrape(known)._save_profile_immediately(_row())

    assert _stored(known) == KNOWN


def test_the_end_of_run_save_leaves_it_as_it_was_too(known):
    scrape = _Scrape(known)
    scrape.scraped_profiles = [_row()]

    scrape._save_to_database()

    assert _stored(known) == KNOWN


def test_a_visit_that_did_not_read_a_key_leaves_it_absent():
    """No `followers_count` in the answer, no About fields (no `fetchLocation`)."""
    visit = {"username": "user_1", "following_count": 57, "posts_count": 79, "is_private": False,
             "is_verified": True, "biography": "bio_1", "full_name": "name_1", "business_category": None,
             "website": None, "linked_accounts": []}
    scrape = _Scrape(db=None, visit_answer=visit)
    profile_data = _row()

    assert scrape._capture_profile_on_screen("user_1", profile_data) is None

    not_read = {"followers_count", "date_joined", "account_based_in", "business_category", "website"}
    assert not not_read & profile_data.keys()
    assert profile_data["following_count"] == 57
    assert profile_data["is_private"] is False


def test_what_the_visit_did_not_read_keeps_its_known_value_in_the_base(known):
    visit = {"username": "user_1", "following_count": 57, "posts_count": 79, "is_private": False,
             "is_verified": True, "biography": "bio_2", "full_name": "name_1", "business_category": None,
             "website": None, "linked_accounts": []}
    scrape = _Scrape(known, visit_answer=visit)
    profile_data = _row()
    scrape._capture_profile_on_screen("user_1", profile_data)

    scrape._save_profile_immediately(profile_data)

    assert _stored(known) == {**KNOWN, "following_count": 57, "posts_count": 79, "is_private": False,
                              "biography": "bio_2"}
