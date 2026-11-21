"""The Lab's workflow bench passes the account on the phone to the scraping, as the app's run does.

Since 2026-11-21 the scraping neither harvests nor visits the account it runs as: the app puts the
account on the phone in the run's file (`accountUsername`, a host key) and the reader passes it to the
workflow (`account_username`). The bench built its own scraping file and never put it there: a bench
run of the likers of a post the account had liked opened its own profile and kept it as a profile
scraped, the behaviour the run no longer has.

The bench file is read as the app writes it, through the bench's real reader and dispatcher, down to
the file the production scraping receives; the scraping itself is played by a double that keeps it.
"""

from __future__ import annotations

import types

import pytest

import bridges.instagram.scraping.workflow as scraping_bridge
from bridges.tools.lab.workflow_test.config.request import load_workflow_test_request
from bridges.tools.lab.workflow_test.execution.dispatcher import dispatch_workflow
from taktik.core.social_media.instagram.workflows.scraping.payload import scraping_config_from_payload


class _Ipc:
    def send(self, *_args, **_kwargs):
        pass


_TRACER = types.SimpleNamespace(begin_step=lambda *a, **k: None, end_step=lambda *a, **k: None)


def _scraping_file(monkeypatch, bench_file: dict) -> dict:
    """The file the production scraping receives from a bench run of `bench_file`."""
    received = []

    def run_scraping_workflow(config, connect=None):
        received.append(config)
        return {"success": True, "totalScraped": 0}

    monkeypatch.setattr(scraping_bridge, "run_scraping_workflow", run_scraping_workflow)
    request = load_workflow_test_request(_Ipc(), bench_file)
    dispatch_workflow(
        app_name=request.app_name,
        workflow_type=request.workflow_type,
        target=request.target,
        limits=request.limits,
        probabilities=request.probabilities,
        session_duration=request.session_duration,
        delays=request.delays,
        account_username=request.account_username,
        conn=types.SimpleNamespace(device_manager=None),
        device=None,
        tracer=_TRACER,
        ipc=_Ipc(),
    )
    assert len(received) == 1
    return received[0]


@pytest.mark.parametrize("workflow", ["scrape_account", "scrape_hashtag", "scrape_post_url", "scrape_profile_posts"])
def test_the_account_on_the_phone_reaches_the_scraping(monkeypatch, workflow):
    scraping_file = _scraping_file(monkeypatch, {
        "device_id": "bench-phone", "app": "instagram", "workflow": workflow,
        "target": "target_account", "accountUsername": "run_account",
    })

    assert scraping_file["accountUsername"] == "run_account"
    assert scraping_config_from_payload(scraping_file)["account_username"] == "run_account"


def test_a_bench_file_without_an_account_passes_none(monkeypatch):
    scraping_file = _scraping_file(monkeypatch, {
        "device_id": "bench-phone", "app": "instagram", "workflow": "scrape_account", "target": "target_account",
    })

    assert "accountUsername" not in scraping_file
    assert "account_username" not in scraping_config_from_payload(scraping_file)


class _Dispatched(Exception):
    """Raised by the dispatcher's double: the entry handed it the request, nothing more to run."""


def test_the_bench_entry_hands_the_account_to_the_dispatcher(monkeypatch):
    import bridges.tools.lab.workflow_test_bridge as entry

    handed = {}

    def dispatch_workflow(**kwargs):
        handed.update(kwargs)
        raise _Dispatched()

    monkeypatch.setattr(entry, "setup_log_sink", lambda ipc: None)
    monkeypatch.setattr(entry, "setup_action_hooks", lambda ipc: None)
    monkeypatch.setattr(entry, "prepare_workflow_test_session", lambda request, ipc: types.SimpleNamespace(
        connection=None, device=None, tracer=_TRACER))
    monkeypatch.setattr(entry, "dispatch_workflow", dispatch_workflow)

    with pytest.raises(_Dispatched):
        entry.run_workflow_test(_Ipc(), {
            "device_id": "bench-phone", "app": "instagram", "workflow": "scrape_account",
            "target": "target_account", "accountUsername": "run_account",
        })

    assert handed["account_username"] == "run_account"
