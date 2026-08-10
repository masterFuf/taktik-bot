"""A visited public profile must be recorded as processed in DB even when no
interaction happens (probability skip).

Regression: `_process_profile_on_screen` only called `mark_profile_as_processed`
when `actually_interacted` was True. A visited-but-not-interacted profile left no
`interactions` row, so the `already_processed` check missed it and a later pass /
followers-list re-scroll re-visited and re-qualified the same profile. Confirmed on
the live DB: @sample_profile was visited once with no row, then fully
re-processed ~5 min later.
"""

import pytest

from taktik.core.social_media.instagram.actions.core.base_business import profile_processing
from taktik.core.social_media.instagram.actions.core.base_business.profile_processing import (
    ProfileProcessingMixin,
    ProfileProcessingResult,
)


class _Logger:
    def debug(self, *a, **k): pass
    def info(self, *a, **k): pass
    def success(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass


class _ProfileBusiness:
    def get_complete_profile_info(self, username=None, navigate_if_needed=False, enrich=False, **kwargs):
        # Public, suitable profile.
        return {'username': username, 'is_private': False, 'followers_count': 100}


class _FilteringBusiness:
    def apply_comprehensive_filter(self, profile_data, filter_criteria):
        return {'suitable': True, 'reasons': []}


class _StatsManager:
    def increment(self, *a, **k): pass


class _Probe(ProfileProcessingMixin):
    def __init__(self, interacted: bool, interaction=None):
        self.logger = _Logger()
        self.profile_business = _ProfileBusiness()
        self.filtering_business = _FilteringBusiness()
        self.stats_manager = _StatsManager()
        self._interacted = interacted
        self._interaction = interaction

    def _perform_interactions_on_profile(self, username, config, profile_data=None):
        return self._interaction or {'actually_interacted': self._interacted}

    def _record_filtered_in_db(self, *a, **k):
        pass


@pytest.fixture
def captured_marks(monkeypatch):
    calls = []
    monkeypatch.setattr(
        profile_processing.InstagramWorkflowStateService,
        'mark_profile_as_processed',
        staticmethod(lambda username, source, account_id=None, session_id=None: calls.append(username) or True),
    )
    return calls


def test_visited_but_not_interacted_is_marked_processed(captured_marks):
    probe = _Probe(interacted=False)
    result = probe._process_profile_on_screen(
        'sample_profile', {}, source_type='FOLLOWER', source_name='@target', account_id=6563, session_id=1
    )
    assert result.status == ProfileProcessingResult.SKIPPED_PROBABILITY
    assert captured_marks == ['sample_profile']  # recorded despite no interaction


def test_interacted_profile_is_marked_processed(captured_marks):
    probe = _Probe(interacted=True)
    result = probe._process_profile_on_screen(
        'alice', {}, source_type='FOLLOWER', source_name='@target', account_id=6563, session_id=1
    )
    assert result.status == ProfileProcessingResult.SUCCESS
    assert captured_marks == ['alice']


def test_post_entry_failure_is_retryable_and_not_marked_processed(captured_marks):
    probe = _Probe(
        interacted=False,
        interaction={
            'actually_interacted': False,
            'technical_failure': True,
            'failure_stage': 'post_entry',
        },
    )
    result = probe._process_profile_on_screen(
        'retry_me', {}, source_type='FOLLOWER', source_name='@target',
        account_id=6563, session_id=1,
    )

    assert result.status == ProfileProcessingResult.ERROR_INTERACTION
    assert result.was_error is True
    assert result.error_message == 'Interaction failed at post_entry'
    assert captured_marks == []
