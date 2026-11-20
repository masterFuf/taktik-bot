"""A hand-picked profile the run could not open is told to the app, with the truth of why.

Before: the loop skipped it with a `step_metric` (`profile_list_decision`, `reason: "error"`) no screen
reads, and the panel's error counter stayed at 0 (direct run of 2026-11-17, an absent handle). TikTok's
loop of the same mode already told its panel. Now the loop counts the error where the panel reads it
(`stats_manager.add_error`, the `instagram_stats` line) and sends `profile_skipped` with the reason
the navigation gave: `not_found` only when the answered search lists the account nowhere,
`search_slow` when it was still loading (the account may exist: nothing is written of it), else
`navigation_failed`.
"""

from types import SimpleNamespace

import pytest
from loguru import logger

from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.social_media.instagram.actions.atomic.navigation.search_results import (
    ProfileNavigationFailure,
    ProfileNavigationFailureReason as Reason,
)
from taktik.core.social_media.instagram.actions.base.base_business.profile_processing import (
    ProfileProcessingResult,
)
from taktik.core.social_media.instagram.workflows.automation.profile_list import workflow as profile_list
from taktik.core.social_media.instagram.workflows.automation.profile_list import ProfileListWorkflowMixin


@pytest.fixture(autouse=True)
def _no_profile_known(monkeypatch):
    monkeypatch.setattr(InstagramWorkflowStateService, 'is_profile_skippable',
                        staticmethod(lambda *args, **kwargs: (False, None)))


class _Loop(ProfileListWorkflowMixin):
    """The real loop, on a pipeline whose navigation fails with the reason given per profile."""

    def __init__(self, failures):
        self.logger = logger
        self.session_manager = None
        self.automation = None
        self.failures = failures
        self.errors = []
        self.stats_manager = SimpleNamespace(
            increment=lambda *args, **kwargs: None,
            add_error=self.errors.append,
            display_stats=lambda *args, **kwargs: None,
            display_final_stats=lambda *args, **kwargs: None,
        )

    def _process_profile_on_screen(self, username, config, **kwargs):
        result = ProfileProcessingResult(ProfileProcessingResult.ERROR_NO_DATA, username)
        result.navigation_failure = self.failures[username]
        return result

    def _get_session_id(self):
        return None

    def _maybe_take_break(self):
        return None


def test_each_profile_not_opened_is_told_with_its_reason(monkeypatch):
    told = []
    monkeypatch.setattr(profile_list.IPCEmitter, 'emit_profile_skipped',
                        staticmethod(lambda username, reason='', detail=None: told.append((username, reason))))
    loop = _Loop({
        'absent': ProfileNavigationFailure('search', Reason.NOT_LISTED),
        'slow': ProfileNavigationFailure('search', Reason.SEARCH_SLOW),
        'tapped': ProfileNavigationFailure('search', Reason.TAP_NO_EFFECT),
        'unread': None,
    })

    stats = loop.interact_with_profile_list(['absent', 'slow', 'tapped', 'unread'], finalize=False)

    assert told == [('absent', 'not_found'), ('slow', 'search_slow'), ('tapped', 'navigation_failed')]
    assert stats['errors'] == 4 and len(loop.errors) == 4
