"""The one look for a block after a gesture, and the health entry a block leaves.

`look_for_action_block` replaces four copies (followers list, unfollow, profile interactions, the
Instagram autopilot), each with its own guard and log. The account's history is written once per
blocked run, by the witness the platform runtime installs on the latch, whoever saw the block:
before, only the followers list and the unfollow wrote it, so a block seen after a like, a DM or a
TikTok gesture left no trace in `account_restriction_signals`.
"""

import types

from taktik.core.database import account_health
from taktik.core.shared.diagnostics import run_halt
from taktik.core.shared.diagnostics.action_block import look_for_action_block


class _Detector:
    def __init__(self, blocked=False, raises=False):
        self.blocked = blocked
        self.raises = raises
        self.looks = 0

    def is_action_blocked(self):
        self.looks += 1
        if self.raises:
            raise RuntimeError("no dump")
        if self.blocked:
            run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page (words)")
        return self.blocked


def test_a_block_on_screen_stops_the_run():
    assert look_for_action_block(_Detector(blocked=True), after="like", target="someone") is True
    assert run_halt.arret_demande()["code"] == "action_blocked"


def test_a_halt_already_set_answers_without_reading_the_screen():
    run_halt.demander_arret(run_halt.DEVICE_DISCONNECTED, "adb gone")
    detector = _Detector()

    assert look_for_action_block(detector, after="follow") is True
    assert detector.looks == 0


def test_an_unreadable_screen_is_not_a_block():
    assert look_for_action_block(_Detector(raises=True), after="like") is False
    assert look_for_action_block(None, after="like") is False
    assert run_halt.arret_demande() is None


# --- the health entry ---------------------------------------------------------------------------


def _record_into(db, monkeypatch):
    import taktik.core.database.local.service as service

    monkeypatch.setattr(service, "get_local_database", lambda: db)


def test_the_first_block_of_a_run_is_one_entry_of_the_account_history(db, monkeypatch):
    _record_into(db, monkeypatch)
    run_halt.configurer_temoin(account_health.witness_for(
        "tiktok", lambda: "@demo_account", source_type=lambda: "FOR_YOU"))

    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "tiktok (Too many requests)")
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "seen again after the next gesture")

    rows = db.account_restrictions.recent_signals("demo_account", platform="tiktok")
    assert [(row["signal"], row["source_type"]) for row in rows] == [("action_blocked", "FOR_YOU")]


def test_a_lost_phone_says_nothing_about_the_account(db, monkeypatch):
    _record_into(db, monkeypatch)
    run_halt.configurer_temoin(account_health.witness_for("instagram", lambda: "demo_account"))

    run_halt.demander_arret(run_halt.DEVICE_DISCONNECTED, "adb gone")

    assert db.account_restrictions.recent_signals("demo_account", platform="instagram") == []


def test_a_block_seen_before_the_account_is_known_is_not_filed_under_nobody(db, monkeypatch):
    _record_into(db, monkeypatch)

    assert account_health.record_action_block(
        {"code": "action_blocked"}, platform="instagram", account_username="unknown") is False


def test_a_failing_witness_never_undoes_the_stop():
    run_halt.configurer_temoin(lambda halt: 1 / 0)

    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "x")

    assert run_halt.arret_demande()["code"] == "action_blocked"


def test_the_tiktok_start_installs_the_witness(monkeypatch):
    """Every TikTok bridge and the CLI start through `start_tiktok_session`: that is where the
    operated account becomes known, and where the witness is installed."""
    from taktik.core.social_media.tiktok.workflows.runtime import startup

    manager = types.SimpleNamespace(restart=lambda: True,
                                    device_manager=types.SimpleNamespace(device=object()))
    monkeypatch.setattr(startup, "_wait_for_app_surface", lambda *a, **k: True)
    seen = []
    monkeypatch.setattr(account_health, "record_action_block",
                        lambda halt, **kw: seen.append((halt["code"], kw["platform"])))

    startup.start_tiktok_session(manager, fetch_profile=False)
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "tiktok (Too many requests)")

    assert seen == [("action_blocked", "tiktok")]
