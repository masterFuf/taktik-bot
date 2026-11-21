"""A scraping never harvests nor visits the account it runs as.

The scraping had no notion of the account on the phone (`y-propres-posts`, point 2): an enriched
scraping of the likers of a post the account liked opened its own profile and filed it as a scraped
profile. The app now sends the account in the configuration, the field and the path the notifications
already use (`accountUsername`, filled by the host), and the scraping passes its row and its name by
the comparison the Feed and the Hashtag use (`ActionUtils.same_username`).

The screen is the real followers list of the row tap test (Instagram 410, French, anonymized); the
account is given the handle of its first row.
"""

from taktik.core.social_media.instagram.workflows.scraping.payload import scraping_config_from_payload
from unit.social_media.instagram.workflows.scraping.test_scrape_list_row_tap import (
    FIRST_NAME,
    LIST,
    _followers_strategy,
    _Phone,
    _Scraper,
)


def _scraper_of(account):
    phone = _Phone(LIST)
    scraper = _Scraper(phone)
    scraper.config["account_username"] = account
    return scraper, phone


def test_the_row_of_the_run_account_is_neither_harvested_nor_tapped():
    scraper, phone = _scraper_of(f"@{FIRST_NAME.upper()}")

    scraped = scraper._scrape_list(1, "FOLLOWER", "demo", enrich_on_the_fly=True,
                                   strategy=_followers_strategy(phone))

    assert FIRST_NAME not in [profile["username"] for profile in scraped]
    assert FIRST_NAME not in scraper.captured
    assert len(scraped) == 1, "the next row is harvested in its place"


def test_without_an_account_the_first_row_is_harvested():
    scraper, phone = _scraper_of(None)

    scraped = scraper._scrape_list(1, "FOLLOWER", "demo", enrich_on_the_fly=True,
                                   strategy=_followers_strategy(phone))

    assert [profile["username"] for profile in scraped] == [FIRST_NAME]


def test_a_list_of_names_skips_the_run_account():
    scraper, _phone = _scraper_of(FIRST_NAME)

    scraper._scrape_usernames([FIRST_NAME, "other_profile"])

    assert scraper.captured == ["other_profile"]


def test_the_payload_carries_the_account_to_the_workflow():
    config = scraping_config_from_payload({"type": "usernames", "usernames": ["a"], "accountUsername": "acting"})

    assert config["account_username"] == "acting"
