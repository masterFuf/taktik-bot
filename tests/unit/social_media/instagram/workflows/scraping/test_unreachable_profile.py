"""A profile that cannot be opened is named as such, and does not take the run down with it.

Lists saved months ago contain accounts that have since been deleted, banned or renamed. The
search then matches nobody, `get_complete_profile_info` returns None, and the run must say so and
move to the next name — this is the ordinary case for an old list, not an anomaly.

The reason matters as much as the skip: "read empty" blames the screen, and would send an operator
looking for a device problem that does not exist.
"""

from taktik.core.social_media.instagram.workflows.scraping.list_scraping import ScrapingListMixin


class _FakeLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)

    def info(self, *_a, **_k):
        pass

    def debug(self, *_a, **_k):
        pass


class _ProfileManager:
    """Returns whatever the test says the profile page yielded."""

    def __init__(self, result):
        self.result = result
        self.calls = 0

    def get_complete_profile_info(self, **_kwargs):
        self.calls += 1
        return self.result


class _Workflow(ScrapingListMixin):
    def __init__(self, profile_result, config=None):
        self.profile_manager = _ProfileManager(profile_result)
        self.logger = _FakeLogger()
        self.config = config or {}
        # No AI service: the screenshot branch is not what these tests are about.
        self._ai_service = None

    def _get_profile_filter_reason(self, _profile_data):
        return None

    def _has_profile_filters(self):
        return False


def _capture(profile_result, *, navigate, config=None):
    workflow = _Workflow(profile_result, config)
    data = {'username': 'ghost_account'}
    reason = workflow._capture_profile_on_screen(
        username='ghost_account', profile_data=data, navigate=navigate,
    )
    return reason, data, workflow


class TestUnreachableProfile:
    def test_a_profile_we_navigated_to_and_never_reached(self):
        reason, _data, _wf = _capture(None, navigate=True)
        assert reason == 'profile unreachable (deleted, renamed or banned)'

    def test_the_reason_does_not_blame_the_screen(self):
        reason, _data, _wf = _capture(None, navigate=True)
        assert 'read empty' not in reason
        assert 'unreachable' in reason

    def test_it_is_a_skip_not_an_exception(self):
        # The run must carry on to the next name; raising here is what would end it early.
        reason, _data, _wf = _capture(None, navigate=True)
        assert isinstance(reason, str) and reason


class TestTheOtherEmptyCase:
    """Not navigating and reading nothing is the black-screen case — a different diagnosis."""

    def test_caller_owned_navigation_keeps_the_empty_read_reason(self):
        reason, _data, _wf = _capture(None, navigate=False)
        assert reason == 'profile page read empty (screen not loaded)'

    def test_a_profile_that_answers_is_not_skipped(self):
        reason, data, _wf = _capture({
            'followers_count': 120, 'following_count': 80, 'posts_count': 9,
            'biography': 'Photographe', 'full_name': 'Alex',
        }, navigate=True)
        assert reason is None
        assert data['followers_count'] == 120
        assert data['biography'] == 'Photographe'
