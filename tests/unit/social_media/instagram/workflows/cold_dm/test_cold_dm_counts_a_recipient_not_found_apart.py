"""A recipient the search did not open is counted for why, and nothing is written for it.

Before 2026-11-21 every recipient the profile search did not open went into `dms_failed`: an account
that does not exist and a search that had not loaded (network) read the same. The search now says
which (`ProfileNavigationFailure`): a recipient not found is counted `dms_not_found`, a slow search
`dms_search_slow`, neither as a failure. Nothing is written to `sent_dms` for any of them (as before:
only a text the conversation took, or one waiting to be sent, leaves a marker), so another run takes
the recipient of a slow search again.
"""

from __future__ import annotations

import pytest

from taktik.core.social_media.instagram.actions.atomic.navigation.search_results import (
    ProfileNavigationFailure,
    ProfileNavigationFailureReason as Reason,
)
from taktik.core.social_media.instagram.workflows.cold_dm import results
from taktik.core.social_media.instagram.workflows.cold_dm import workflow as module


@pytest.fixture
def markers(monkeypatch):
    written = []
    monkeypatch.setattr(results, "record_sent_dm", lambda *args, **kwargs: written.append(("sent", args)))
    monkeypatch.setattr(results, "record_pending_dm", lambda *args, **kwargs: written.append(("pending", args)))
    return written


def _run(monkeypatch, failures):
    """A run over the recipients of `failures`, each one's search failing that way."""
    monkeypatch.setattr(module, "wait_before_next_cold_dm", lambda **kwargs: None)
    workflow = module.ColdDMWorkflow(object(), object())

    def open_recipient_profile(recipient):
        workflow.recipient_navigation_failure = ProfileNavigationFailure("search", failures[recipient])
        return False

    workflow.open_recipient_profile = open_recipient_profile
    workflow.go_home = lambda: None
    workflow.filter_pending_recipients = lambda recipients, account_id: list(recipients)
    workflow._detect_app_language = lambda: None
    return workflow.run(list(failures), ["Hello there"], account_id=7)


def test_a_recipient_not_found_and_a_slow_search_are_counted_apart_from_failures(monkeypatch, markers):
    summary = _run(monkeypatch, {
        "absent_handle": Reason.NOT_LISTED,
        "slow_handle": Reason.SEARCH_SLOW,
        "untapped_handle": Reason.ROW_NOT_TAPPED,
    })

    assert (summary["dms_not_found"], summary["dms_search_slow"], summary["dms_failed"]) == (1, 1, 1)
    assert summary["dms_sent"] == 0
    assert markers == []

