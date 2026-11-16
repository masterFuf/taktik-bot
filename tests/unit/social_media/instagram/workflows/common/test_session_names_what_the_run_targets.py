"""A run's session says what the run targets, written through the database service.

A run on hand-picked accounts ("Ces comptes", `workflowType: target_profiles`) reached
`create_workflow_session` with the action `interact_with_profiles`, which its table of session
targets did not know: the config path skipped it without a word and the session was written
`USER` / "unknown" (`Auto_USER_unknown_...`), so its history named no account. `USER` would be
wrong too: the app reads a `USER` session as a source whose lists were walked, and draws an edge
from it to every profile met in the run.

The config is built by the production builder from the payload the app sends; the session row
is read back from a temporary base.
"""

from loguru import logger

from taktik.core.social_media.instagram.workflows.automation.config_builder import (
    build_instagram_automation_config,
)
from taktik.core.social_media.instagram.workflows.common import workflow_helpers


class _Automation:
    def __init__(self, account_id, config):
        self.active_account_id = account_id
        self.config = config


def _session_row(db, monkeypatch, raw_config):
    monkeypatch.setattr(workflow_helpers, "get_local_database", lambda: db)
    account_id, _ = db.get_or_create_account("taktik_test")
    config = build_instagram_automation_config(raw_config)
    session_id = workflow_helpers.WorkflowHelpers(_Automation(account_id, config)).create_workflow_session()
    assert session_id
    return db.sessions.query_one(
        "SELECT session_name, target_type, target FROM sessions_unified "
        "WHERE platform = 'instagram' AND legacy_session_id = ?",
        (session_id,),
    )


def test_a_run_on_given_accounts_names_its_first_account(db, monkeypatch):
    row = _session_row(db, monkeypatch, {"workflowType": "target_profiles",
                                         "target": "target_alpha, target_beta"})

    assert row["target_type"] == "PROFILES"
    assert row["target"] == "target_alpha"
    assert row["session_name"].startswith("Auto_PROFILES_target_alpha_")


def test_a_run_on_a_source_account_keeps_its_label(db, monkeypatch):
    row = _session_row(db, monkeypatch, {"workflowType": "target_followers", "target": "target_alpha"})

    assert row["target_type"] == "USER"
    assert row["target"] == "target_alpha"


def test_a_step_the_table_does_not_know_says_so(db, monkeypatch):
    """The config path skipped an unknown step without a word: that silence is how
    `interact_with_profiles` stayed "unknown" for weeks."""
    monkeypatch.setattr(workflow_helpers, "get_local_database", lambda: db)
    account_id, _ = db.get_or_create_account("taktik_test")
    warnings = []
    sink = logger.add(lambda message: warnings.append(message.record["message"]), level="WARNING")
    try:
        helpers = workflow_helpers.WorkflowHelpers(_Automation(account_id, {"actions": [{"type": "not_a_step"}]}))
        assert helpers.create_workflow_session()
    finally:
        logger.remove(sink)

    assert any("Unmapped action type 'not_a_step'" in w for w in warnings)
