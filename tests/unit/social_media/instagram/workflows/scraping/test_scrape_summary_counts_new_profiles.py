"""The end-of-run summary says how many profiles were NEW before the run, and each is saved once.

A scrape saves every kept profile as soon as it is read (`_save_profile_immediately`), then the
end of the run saved the whole list a second time (`_save_to_database`) and counted "new" from that
second save, where every profile already existed: on a fresh base the five runs of 24/10 all said
"Saved 0 new profiles, updated N existing profiles". The second save also wrote a second stats
snapshot of every profile, two points of the series for one reading. The base is a real one
(throwaway file).
"""

from loguru import logger

from taktik.core.social_media.instagram.workflows.scraping.persistence import ScrapingPersistenceMixin


def _profile(username):
    return {"username": username, "source_type": "FOLLOWERS", "source_name": "user_9",
            "scraped_at": "2026-10-24T21:04:30", "followers_count": 10, "following_count": 20,
            "posts_count": 3}


class _Scrape(ScrapingPersistenceMixin):
    def __init__(self, db, save_immediately=True):
        self.local_db = db
        self.config = {}
        self.logger = logger
        self._save_immediately = save_immediately
        self.scraping_session_id = None
        self.scraped_profiles = []

    def keep(self, username):
        """What the list scrape does with a kept profile: append it, then save it at once."""
        profile = _profile(username)
        self.scraped_profiles.append(profile)
        self._save_profile_immediately(profile)


def _snapshots(db, username):
    profile_id = db.get_profile_by_username(username)["profile_id"]
    return db._get_connection().execute(
        "SELECT COUNT(*) FROM profile_stats_history WHERE profile_id = ?", (profile_id,)
    ).fetchone()[0]


def test_profiles_new_before_the_run_are_counted_new(db, capsys):
    scrape = _Scrape(db)
    scrape.keep("user_1")
    scrape.keep("user_2")

    scrape._save_to_database()

    out = capsys.readouterr().out
    assert "Saved 2/2 profiles" in out
    assert "updated" not in out


def test_a_profile_known_before_the_run_is_counted_updated(db, capsys):
    db.save_profile({"username": "user_1"})
    scrape = _Scrape(db)
    scrape.keep("user_1")
    scrape.keep("user_2")

    scrape._save_to_database()

    assert "Saved 1 new profiles, updated 1 existing profiles" in capsys.readouterr().out


def test_a_profile_saved_during_the_run_is_not_saved_again(db):
    scrape = _Scrape(db)
    scrape.keep("user_1")

    scrape._save_to_database()

    assert _snapshots(db, "user_1") == 1


def test_without_the_immediate_save_the_end_of_run_save_writes_them(db, capsys):
    scrape = _Scrape(db, save_immediately=False)
    scrape.keep("user_1")

    scrape._save_to_database()

    assert db.get_profile_by_username("user_1") is not None
    assert _snapshots(db, "user_1") == 1
    assert "Saved 1/1 profiles" in capsys.readouterr().out
