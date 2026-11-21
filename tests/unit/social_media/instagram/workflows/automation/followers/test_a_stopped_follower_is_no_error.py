"""A follower the stop caught is neither an error of the run nor a reason to go back to the list.

The followers loop counted a profile the pipeline filed « run stop requested » in `stats['errors']`,
then went back to the list (a forced back) before its next row read the latch. The pipeline now
says STOPPED, and the loop leaves the screen as it is.
"""

import types

from taktik.core.social_media.instagram.actions.base.base_business.profile_processing import (
    ProfileProcessingResult,
)
from taktik.core.social_media.instagram.workflows.automation.followers.workflows.direct.profile_processing import (
    DirectProfileProcessingMixin,
)


class _Logger:
    def info(self, *a, **k): pass
    def debug(self, *a, **k): pass
    def warning(self, *a, **k): pass


class _Tracker:
    def log_profile_visit(self, *a, **k): pass
    def log_profile_filtered(self, *a, **k): pass


class _Host(DirectProfileProcessingMixin):
    """The real reader of the pipeline's outcome; the tap and the pipeline are scripted."""

    def __init__(self, status):
        self.logger = _Logger()
        self.backs = []
        self._status = status
        self.detection_actions = types.SimpleNamespace(
            click_follower_in_list=lambda username: True,
            wait_for_profile_screen=lambda timeout=0: True,
        )
        self.stats_manager = types.SimpleNamespace(increment=lambda *a, **k: None)

    def _human_like_delay(self, *a, **k): pass
    def _get_session_id(self): return None

    def _process_profile_on_screen(self, username, *a, **k):
        return ProfileProcessingResult(self._status, username)

    def _ensure_on_followers_list(self, target, force_back=False):
        self.backs.append(force_back)
        return True


def _visit(status):
    host = _Host(status)
    stats = {'interacted': 0, 'errors': 0, 'skipped': 0, 'filtered': 0, 'visited': 0}
    outcome = host._process_single_follower_direct(
        "alice", 0, stats, {}, None, "target", 0, 1, 5, _Tracker())
    return host, stats, outcome


def test_a_stopped_follower_is_no_error_and_no_way_back():
    host, stats, outcome = _visit(ProfileProcessingResult.STOPPED)

    assert outcome is False
    assert stats['errors'] == 0
    assert stats['visited'] == 0 and stats['skipped'] == 0, "a stopped profile is no visit either"
    assert host.backs == []


def test_a_follower_that_failed_is_still_an_error_and_the_list_is_found_again():
    host, stats, outcome = _visit(ProfileProcessingResult.ERROR_INTERACTION)

    assert outcome is False
    assert stats['errors'] == 1
    assert host.backs == [True]
