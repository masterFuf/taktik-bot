"""The bench scraping probe must leave no trace.

Scraping only reads, so there is no last tap to hold back — but it normally writes every profile
it finds to the operator's database and drops a CSV on their disk, and it can spend real money on
AI qualification. A diagnostic run doing any of that would be a side effect nobody asked for, so
the three switches are pinned here.
"""
from bridges.compat.diagnostics.runtime.workflow_test.platforms.instagram.workflows.scraping import (
    _bridge_config,
)
from bridges.instagram.scraping.runtime.config import build_scraping_config


def _config(scraping_type, target, limits=None):
    return build_scraping_config(_bridge_config(scraping_type, target, limits or {}, None))


def test_probe_never_persists_exports_or_spends():
    for scraping_type, target in (
        ("target", "someaccount"),
        ("hashtag", "#travel"),
        ("post_url", "https://www.instagram.com/p/ABC123/"),
    ):
        config = _config(scraping_type, target)
        assert config["save_to_db"] is False, scraping_type
        assert config["export_csv"] is False, scraping_type
        assert config["ai_mode"] is False, scraping_type
        assert config["enrich_profiles"] is False, scraping_type


def test_probe_disables_dedup_so_a_second_run_is_not_a_false_success():
    # Left at the default, a re-run would skip every already-known profile, scrape nothing, and
    # still report success — the bench would look healthy while measuring nothing.
    assert _config("target", "someaccount")["rescrape_after_days"] == 0


def test_target_shapes_reach_the_production_config():
    assert _config("target", "someaccount")["target_usernames"] == ["someaccount"]
    # The leading '#' is the operator's notation, not part of the hashtag.
    assert _config("hashtag", "#travel")["hashtags"] == ["travel"]

    post = _config("post_url", "https://www.instagram.com/p/ABC123/")
    assert post["post_urls"] == ["https://www.instagram.com/p/ABC123/"]
    assert post["post_id"] == "ABC123"


def test_a_list_of_targets_is_accepted_as_is():
    assert _config("target", ["a", "b"])["target_usernames"] == ["a", "b"]


def test_limits_drive_the_profile_cap():
    assert _config("target", "x", {"maxProfiles": 3})["max_profiles"] == 3
    # Absent or null limits must not become an unbounded run on a diagnostic.
    assert _config("target", "x", {"maxProfiles": None})["max_profiles"] == 10
