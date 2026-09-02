"""Only an account we could not OPEN gets marked — never one we simply did not want.

Every other skip reason is a decision about a living profile: too few followers, private, already
followed. Marking those would quietly retire perfectly good accounts from every future run, which
is the opposite of what the mark is for.
"""

from taktik.core.social_media.instagram.workflows.scraping.list_scraping import (
    UNREACHABLE_REASON,
    ScrapingListMixin,
)


class _FakeDb:
    def __init__(self):
        self.marked = []
        self.cleared = []

    def mark_profile_unreachable(self, username, platform='instagram'):
        self.marked.append(username)
        return True

    def clear_profile_unreachable(self, username, platform='instagram'):
        self.cleared.append(username)
        return True

    def profile_exists_in_db(self, *_a, **_k):
        return False


class _FakeLogger:
    def info(self, *_a, **_k):
        pass

    def warning(self, *_a, **_k):
        pass

    def debug(self, *_a, **_k):
        pass


class _Workflow(ScrapingListMixin):
    """Drives _scrape_usernames with a scripted answer per profile."""

    def __init__(self, reason_by_user):
        self.reason_by_user = reason_by_user
        self.db = _FakeDb()
        self.logger = _FakeLogger()
        self.config = {'rescrape_after_days': 0}
        self.scraped_profiles = []

    def _local_db(self):
        return self.db

    def _should_continue(self):
        return True

    def _save_profile_immediately(self, _profile_data):
        # No AI service on this workflow, so the id only has to be falsy-or-not.
        return None

    def _capture_profile_on_screen(self, username, profile_data, **_kwargs):
        return self.reason_by_user.get(username)


def _run(reason_by_user, usernames):
    workflow = _Workflow(reason_by_user)
    workflow._scrape_usernames(usernames, source_name='test')
    return workflow.db


class TestOnlyUnreachableIsMarked:
    def test_an_unreachable_profile_is_marked(self):
        db = _run({'ghost': UNREACHABLE_REASON}, ['ghost'])
        assert db.marked == ['ghost']

    def test_a_filtered_but_living_profile_is_not(self):
        # These accounts exist and answered; they were simply not wanted this time.
        living = {
            'small_account': 'Too few followers (42 < 100)',
            'locked': 'Private profile',
            'known': 'Already followed by us',
        }
        db = _run(living, list(living))
        assert db.marked == []

    def test_a_black_screen_is_not_a_dead_account(self):
        # The empty-read reason describes a screen that did not load, not an account that is gone.
        db = _run({'someone': 'profile page read empty (screen not loaded)'}, ['someone'])
        assert db.marked == []

    def test_a_profile_that_answers_clears_its_mark(self):
        db = _run({'alive': None}, ['alive'])
        assert db.cleared == ['alive']
        assert db.marked == []

    def test_one_dead_profile_does_not_stop_the_others(self):
        db = _run({'ghost': UNREACHABLE_REASON, 'alive': None}, ['ghost', 'alive'])
        assert db.marked == ['ghost']
        assert db.cleared == ['alive']
