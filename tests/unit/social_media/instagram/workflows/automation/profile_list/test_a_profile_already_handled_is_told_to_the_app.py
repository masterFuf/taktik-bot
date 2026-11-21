"""A hand-picked profile this account already handled is told to the app, as the other loops tell it.

Before: « Ces comptes » skipped it before any navigation (right), but said so only with a `step_metric`
(`profile_list_decision`, `already_known`) no screen reads: the « Déjà connus » tile, which counts the
`profile_skipped` lines, stayed at 0. The followers and likers loops send `profile_skipped` with the
reason the base gave (`already_processed`, `already_filtered`) and its detail; this loop does too,
through the same call.
"""

from types import SimpleNamespace

from loguru import logger

from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.social_media.instagram.actions.base.ipc.emitter import IPCEmitter
from taktik.core.social_media.instagram.workflows.automation.profile_list import ProfileListWorkflowMixin

KNOWN = {"engaged": "already_processed", "rejected": "already_filtered"}


class _Loop(ProfileListWorkflowMixin):
    """The real loop: every profile it would visit is a failure of the test."""

    def __init__(self):
        self.logger = logger
        self.session_manager = None
        self.automation = None
        self.stats_manager = SimpleNamespace(
            increment=lambda *args, **kwargs: None,
            add_error=lambda *args, **kwargs: None,
            display_stats=lambda *args, **kwargs: None,
            display_final_stats=lambda *args, **kwargs: None,
        )

    def _process_profile_on_screen(self, username, config, **kwargs):
        raise AssertionError(f"@{username} is known: the loop must not open it")

    def _get_session_id(self):
        return None

    def _maybe_take_break(self):
        return None


def test_each_profile_already_handled_is_told_with_the_reason_of_the_base(monkeypatch):
    monkeypatch.setattr(InstagramWorkflowStateService, "is_profile_skippable",
                        staticmethod(lambda username, account_id, **kwargs: (True, KNOWN[username])))
    monkeypatch.setattr(InstagramWorkflowStateService, "get_skip_detail",
                        staticmethod(lambda username, account_id, reason: f"detail of {username}"))
    told = []
    monkeypatch.setattr(IPCEmitter, "emit_profile_skipped",
                        staticmethod(lambda username, reason="", detail=None: told.append((username, reason, detail))))
    stats = _Loop().interact_with_profile_list(["engaged", "rejected"], account_id=7, finalize=False)

    assert told == [("engaged", "already_processed", "detail of engaged"),
                    ("rejected", "already_filtered", "detail of rejected")]
    assert (stats["already_processed"], stats["already_filtered"], stats["errors"]) == (1, 1, 0)
