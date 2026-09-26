"""Cold DM: « Ignorer les comptes privés » and « Ignorer les comptes certifiés » now decide.

Both settings reached `cold_dm_bridge` and were read by nobody. A private profile was ALWAYS
skipped, including on a scheduler node whose form said « do not skip », and the certified badge
was never looked at. These tests hold the decision (core, no device) and the bridge adapter that
reads the screen and the payload.
"""

from types import SimpleNamespace

import pytest

from taktik.core.social_media.instagram.workflows.cold_dm.recipient_policy import (
    SKIP_PRIVATE,
    SKIP_PRIVATE_NO_MESSAGE,
    SKIP_VERIFIED,
    ColdDmRecipientPolicy,
    cold_dm_skip_reason,
)


# ------------------------------------------------------------------------------------ decision

def _reason(policy, private=False, verified=False, message=True):
    return cold_dm_skip_reason(policy, is_private=private, is_verified=verified,
                               has_message_button=message)


def test_defaults_are_the_behaviour_the_bridge_always_had():
    policy = ColdDmRecipientPolicy()
    assert _reason(policy, private=True) == SKIP_PRIVATE
    assert _reason(policy, verified=True) is None


def test_a_private_profile_is_tried_when_the_operator_allows_it_and_instagram_offers_it():
    assert _reason(ColdDmRecipientPolicy(skip_private=False), private=True) is None


def test_a_private_profile_without_message_button_is_a_skip_not_a_failure():
    policy = ColdDmRecipientPolicy(skip_private=False)
    assert _reason(policy, private=True, message=False) == SKIP_PRIVATE_NO_MESSAGE


def test_certified_accounts_are_skipped_when_asked():
    assert _reason(ColdDmRecipientPolicy(skip_verified=True), verified=True) == SKIP_VERIFIED


def test_a_public_profile_without_message_button_stays_a_failure_for_the_caller():
    assert _reason(ColdDmRecipientPolicy(), message=False) is None


# ------------------------------------------------------------------------- bridge: the screen

class _Node:
    """A uiautomator2 selection of at most one node."""

    def __init__(self, exists):
        self.exists = exists
        self.clicks = 0
        self.info = {"resourceName": ""}

    @property
    def count(self):
        return 1 if self.exists else 0

    def __getitem__(self, _index):
        return self

    def click(self):
        self.clicks += 1


class _Device:
    """Answers `device(text=/description=/resourceId=/textContains=)` from a fixed screen."""

    def __init__(self, *, private=False, message=True):
        self.private = private
        self.message = message
        self.message_node = _Node(True)

    def __call__(self, **kwargs):
        from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS

        if kwargs.get("resourceId") == PROFILE_SELECTORS.private_empty_state_resource_id:
            return _Node(self.private)
        if "textContains" in kwargs:
            return _Node(False)
        if self.message and (kwargs.get("text") in PROFILE_SELECTORS.message_button_text_labels):
            return self.message_node
        return _Node(False)


def _runtime(*, private=False, message=True, verified=False):
    from taktik.core.social_media.instagram.workflows.cold_dm.navigation import ColdDMNavigationMixin

    reads = []

    class _Runtime(ColdDMNavigationMixin):
        def __init__(self):
            self.device = _Device(private=private, message=message)

        def _cold_dm_detection(self):
            return SimpleNamespace(is_verified_account=lambda: reads.append("badge") or verified,
                                   wait_for_profile_screen=lambda **_: True)

    return _Runtime(), reads


def test_the_bridge_skips_a_private_profile_by_default(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    runtime, _ = _runtime(private=True)
    assert runtime.open_dm_from_profile(ColdDmRecipientPolicy()) == SKIP_PRIVATE
    assert runtime.device.message_node.clicks == 0


def test_the_bridge_opens_the_dm_of_a_private_profile_when_allowed(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    runtime, _ = _runtime(private=True)
    assert runtime.open_dm_from_profile(ColdDmRecipientPolicy(skip_private=False)) is True
    assert runtime.device.message_node.clicks == 1


def test_the_bridge_reads_the_badge_only_when_asked(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    runtime, reads = _runtime(verified=True)
    assert runtime.open_dm_from_profile(ColdDmRecipientPolicy()) is True
    assert reads == []

    runtime, reads = _runtime(verified=True)
    assert runtime.open_dm_from_profile(ColdDmRecipientPolicy(skip_verified=True)) == SKIP_VERIFIED
    assert reads == ["badge"] and runtime.device.message_node.clicks == 0


# ------------------------------------------------------- the launcher: the payload (bridge and CLI)

@pytest.mark.parametrize("payload, expected", [
    ({}, ColdDmRecipientPolicy(skip_private=True, skip_verified=False)),
    ({"skipPrivateAccounts": False}, ColdDmRecipientPolicy(skip_private=False)),
    ({"skipVerifiedAccounts": True}, ColdDmRecipientPolicy(skip_verified=True)),
])
def test_the_page_settings_reach_the_workflow(payload, expected):
    from taktik.core.social_media.instagram.workflows.cold_dm.agent_handler import (
        ColdDmRuntime,
        run_instagram_cold_dm,
    )

    seen = {}

    class _Workflow:
        def __init__(self, *a, **k):
            pass

        def run(self, *args, recipient_policy=None, **kwargs):
            seen["policy"] = recipient_policy
            return {"success": True}

    run_instagram_cold_dm(
        {"deviceId": "dev", "recipients": ["a"], "messages": ["hi"], **payload},
        runtime=ColdDmRuntime(device=None, device_manager=None, keyboard=None),
        workflow_factory=_Workflow,
    )

    assert seen["policy"] == expected


# --------------------------------------------------------------------------------------- Lab

def test_the_lab_check_runs_the_bridge_evaluation_without_tapping():
    from bridges.compat.diagnostics.actions.instagram.dm import cold_dm_check_profile

    device = _Device(private=True)
    bundle = SimpleNamespace(device=SimpleNamespace(device=device),
                             detection=SimpleNamespace(is_verified_account=lambda: False,
                                                       wait_for_profile_screen=lambda **_: True))

    skipped = cold_dm_check_profile(bundle, {})
    tried = cold_dm_check_profile(bundle, {"skipPrivate": "false"})

    assert skipped["details"]["skip_reason"] == SKIP_PRIVATE
    assert tried["details"]["skip_reason"] is None
    assert device.message_node.clicks == 0


def _lab_send(monkeypatch, device, params):
    """The Lab send, with the search steps and the composer as the only stand-ins."""
    from bridges.compat.diagnostics.actions.instagram.dm import send_cold_dm
    from taktik.core.social_media.instagram.workflows.cold_dm.workflow import ColdDMWorkflow

    monkeypatch.setattr("time.sleep", lambda *_: None)
    sent = []
    monkeypatch.setattr(ColdDMWorkflow, "navigate_to_search", lambda self: True)
    monkeypatch.setattr(ColdDMWorkflow, "search_user", lambda self, username: True)
    monkeypatch.setattr(ColdDMWorkflow, "send_message", lambda self, message: sent.append(message) or True)
    bundle = SimpleNamespace(device=SimpleNamespace(device=device),
                             detection=SimpleNamespace(is_verified_account=lambda: False,
                                                       wait_for_profile_screen=lambda **_: True))
    return send_cold_dm(bundle, params), sent


def test_the_lab_send_goes_through_the_bridge_steps_and_policy(monkeypatch):
    """Same steps as the bridge (`ColdDMWorkflow.reach_and_send`): a private profile is left alone
    by default, and nothing is typed."""
    result, sent = _lab_send(monkeypatch, _Device(private=True), {"username": "@ana", "text": "Bonjour"})

    assert result["success"] is False
    assert result["details"]["outcome"] == SKIP_PRIVATE
    assert sent == []


def test_the_lab_send_sends_the_text_once_the_conversation_is_open(monkeypatch):
    device = _Device()
    result, sent = _lab_send(monkeypatch, device, {"username": "ana", "text": "Bonjour"})

    assert result["success"] is True
    assert result["details"]["outcome"] == "sent"
    assert sent == ["Bonjour"]
    assert device.message_node.clicks == 1
