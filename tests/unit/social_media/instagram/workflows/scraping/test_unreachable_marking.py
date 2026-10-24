"""Only an account we could not OPEN gets marked — never one we simply did not want.

Every other skip reason is a decision about a living profile: too few followers, private, already
followed. Marking those would quietly retire perfectly good accounts from every future run, which
is the opposite of what the mark is for.
"""

from types import SimpleNamespace

from taktik.core.social_media.instagram.workflows.scraping.list_scraping import (
    NOT_OPENED_OFFLINE_REASON,
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


class _NotOpened(ScrapingListMixin):
    """`_capture_profile_on_screen` of a profile the visit could not open (the profile manager
    answers None, as it does when the profile shows no handle), on a phone whose ping answers
    `ping`."""

    def __init__(self, ping):
        self.logger = _FakeLogger()
        self.config = {}
        self.device_manager = SimpleNamespace(device_id="phone-1")
        self.profile_manager = SimpleNamespace(get_complete_profile_info=lambda **_k: None)
        self.pinged = []
        self.ping = ping

    def measure(self, device_id):
        self.pinged.append(device_id)
        return self.ping


NO_ROUTE = {"rtt_ms": None, "packet_loss_pct": None, "received": 0, "unreachable": True}
ONLINE = {"rtt_ms": 40.0, "packet_loss_pct": 0.0, "received": 3, "unreachable": False}


class TestAProfileNotOpenedWithoutNetworkIsNotGone:
    """Phone session of 2026-10-24: without network, a profile opens blank, no handle, and
    Instagram writes « Utilisateur(ice) introuvable » on it (`no_found_text`), the words it shows
    for an account that does not exist. The visit is not verified and returns nothing; the scrape
    by usernames then called the account deleted, renamed or banned and marked it unreachable,
    which retires it from every later run. A profile not opened is that only when the phone had
    a route: its ping says so."""

    def _reason(self, monkeypatch, ping):
        import taktik.core.social_media.instagram.workflows.scraping.list_scraping as list_scraping

        workflow = _NotOpened(ping)
        monkeypatch.setattr(list_scraping, "measure_network_baseline", workflow.measure, raising=False)
        reason = workflow._capture_profile_on_screen(username="someone", profile_data={}, navigate=True)
        return reason, workflow.pinged

    def test_without_network_the_profile_is_not_read_not_gone(self, monkeypatch):
        reason, pinged = self._reason(monkeypatch, NO_ROUTE)
        assert reason == NOT_OPENED_OFFLINE_REASON
        assert pinged == ["phone-1"]
        assert _run({"someone": reason}, ["someone"]).marked == []

    def test_with_network_the_profile_not_opened_is_unreachable(self, monkeypatch):
        reason, _ = self._reason(monkeypatch, ONLINE)
        assert reason == UNREACHABLE_REASON

    def test_a_network_that_cannot_be_measured_marks_nothing(self, monkeypatch):
        reason, _ = self._reason(monkeypatch, None)
        assert reason == NOT_OPENED_OFFLINE_REASON
