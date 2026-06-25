"""Every profile processed through the shared `_process_profile_on_screen`
pipeline must emit a `profile_visit` IPC event — that event opens the live card
in the Taktik Agent copilot. Centralizing the emit here is what makes the copilot
work for ALL profile workflows (Target, Hashtag, Post Likers, post_url), not just
Target.

Regression context: the visit emit used to live only in the Target-specific
callers (`followers/.../direct/profile_processing.py`, `followers/.../legacy.py`),
so the sibling workflows (which share `_process_profile_on_screen` via
`LikersWorkflowBase`) opened no card even though they already emitted
plan/filter/private/story. The emit is now centralized in the shared pipeline and
the Target-specific duplicates removed.
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
    def __init__(self, private=False):
        self._private = private

    def get_complete_profile_info(self, username=None, navigate_if_needed=False, enrich=False, **kwargs):
        return {'username': username, 'is_private': self._private, 'followers_count': 100}


class _FilteringBusiness:
    def __init__(self, suitable=True):
        self._suitable = suitable

    def apply_comprehensive_filter(self, profile_data, filter_criteria):
        return {'suitable': self._suitable, 'reasons': [] if self._suitable else ['Too few posts (0 < 3)']}


class _StatsManager:
    def increment(self, *a, **k): pass


class _Probe(ProfileProcessingMixin):
    def __init__(self, *, interacted=True, private=False, suitable=True):
        self.logger = _Logger()
        self.profile_business = _ProfileBusiness(private=private)
        self.filtering_business = _FilteringBusiness(suitable=suitable)
        self.stats_manager = _StatsManager()
        self._interacted = interacted

    def _perform_interactions_on_profile(self, username, config, profile_data=None):
        return {'actually_interacted': self._interacted}

    def _record_filtered_in_db(self, *a, **k):
        pass


@pytest.fixture
def captured_visits(monkeypatch):
    calls = []
    monkeypatch.setattr(
        profile_processing.InstagramWorkflowStateService,
        'mark_profile_as_processed',
        staticmethod(lambda *a, **k: True),
    )
    monkeypatch.setattr(
        profile_processing.IPCEmitter,
        'emit_profile_visit',
        staticmethod(lambda username: calls.append(username)),
    )
    return calls


def test_visit_emitted_for_interacted_profile(captured_visits):
    result = _Probe(interacted=True)._process_profile_on_screen(
        'alice', {}, source_type='HASHTAG', source_name='#travel'
    )
    assert result.status == ProfileProcessingResult.SUCCESS
    assert captured_visits == ['alice']


def test_visit_emitted_for_filtered_profile(captured_visits):
    # Post Likers / Hashtag: a profile filtered on criteria still opens a card.
    result = _Probe(suitable=False)._process_profile_on_screen(
        'bob', {}, source_type='POST_URL', source_name='https://insta/p/x'
    )
    assert result.status == ProfileProcessingResult.FILTERED_CRITERIA
    assert captured_visits == ['bob']


def test_visit_emitted_for_private_profile(captured_visits):
    result = _Probe(private=True)._process_profile_on_screen(
        'carol', {}, source_type='HASHTAG', source_name='#fit'
    )
    assert result.status == ProfileProcessingResult.FILTERED_PRIVATE
    assert captured_visits == ['carol']
