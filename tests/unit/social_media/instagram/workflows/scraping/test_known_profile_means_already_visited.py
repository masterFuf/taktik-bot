"""A profile the base only knows by its handle is still to visit.

A like given in the Feed is filed under the post's author (`record_interaction`), which writes a row
holding the handle and nothing else. The scraping's dedup read that row as "already scraped" and, with
its default ("never re-scrape"), never opened the profile: it stayed empty for good. For a run that
opens profiles, known now means visited. A run that only collects names comes for the name, and keeps
skipping it.

The list is a real followers list of Instagram 410.0.0.53.71 in French, walked by the production loop;
the base is a real one, built by the schema.
"""

from unit.social_media.instagram.workflows.scraping.test_scrape_list_row_tap import (
    FIRST_NAME,
    LIST,
    _followers_strategy,
    _Phone,
    _Scraper,
)

STORED = "a_stored_handle"
READ_ON_ITS_PAGE = {"followers_count": 120, "biography": "A bio"}


class _ScraperOnBase(_Scraper):
    def __init__(self, phone, base, rescrape_after_days=None):
        super().__init__(phone)
        self.base = base
        self.config = {"rescrape_after_days": rescrape_after_days}
        self.preexisted = {}

    def _local_db(self):
        return self.base

    def _capture_profile_on_screen(self, username, **kwargs):
        self.preexisted[username] = kwargs["profile_preexisted"]
        return super()._capture_profile_on_screen(username, **kwargs)


def _walk_the_list(base, enrich):
    phone = _Phone(LIST)
    scraper = _ScraperOnBase(phone, base)
    scraped = scraper._scrape_list(1, "FOLLOWER", "demo", enrich_on_the_fly=enrich, strategy=_followers_strategy(phone))
    return scraper, [profile["username"] for profile in scraped]


def _qualify(base, rescrape_after_days=None):
    scraper = _ScraperOnBase(_Phone(LIST), base, rescrape_after_days)
    scraper._scrape_usernames([STORED], source_name="demo")
    return scraper


def test_a_run_that_opens_profiles_visits_a_row_holding_only_the_handle(db):
    db.get_or_create_profile({"username": FIRST_NAME})
    scraper, names = _walk_the_list(db, enrich=True)
    assert scraper.captured == [FIRST_NAME]
    assert names == [FIRST_NAME]


def test_a_run_that_opens_profiles_skips_a_profile_already_visited(db):
    db.get_or_create_profile({"username": FIRST_NAME, **READ_ON_ITS_PAGE})
    scraper, _names = _walk_the_list(db, enrich=True)
    assert FIRST_NAME not in scraper.captured


def test_a_page_that_could_not_be_opened_is_not_tried_again(db):
    db.get_or_create_profile({"username": FIRST_NAME})
    db.mark_profile_unreachable(FIRST_NAME)
    scraper, _names = _walk_the_list(db, enrich=True)
    assert FIRST_NAME not in scraper.captured


def test_a_run_that_only_collects_names_keeps_skipping_a_known_name(db):
    db.get_or_create_profile({"username": FIRST_NAME})
    _scraper, names = _walk_the_list(db, enrich=False)
    assert FIRST_NAME not in names


def test_a_run_that_only_collects_names_collects_a_new_one(db):
    _scraper, names = _walk_the_list(db, enrich=False)
    assert names == [FIRST_NAME]


def test_the_qualification_of_a_list_visits_a_row_holding_only_the_handle(db):
    db.get_or_create_profile({"username": STORED})
    assert _qualify(db).captured == [STORED]


def test_the_qualification_of_a_list_skips_a_profile_already_visited(db):
    db.get_or_create_profile({"username": STORED, **READ_ON_ITS_PAGE})
    assert _qualify(db).captured == []


def test_stats_only_does_not_apply_to_a_profile_never_visited(db):
    """`stats_only` keeps what an earlier visit paid for; a handle alone holds nothing to keep."""
    db.get_or_create_profile({"username": STORED})
    assert _qualify(db, rescrape_after_days=30).preexisted == {STORED: False}


def test_stats_only_applies_to_a_profile_visited_before_the_window(db):
    db.get_or_create_profile({"username": STORED, **READ_ON_ITS_PAGE})
    db.profiles.execute(
        "UPDATE social_profiles SET created_at = datetime('now', '-60 days') WHERE username = ?",
        (STORED,),
    )
    assert _qualify(db, rescrape_after_days=30).preexisted == {STORED: True}
