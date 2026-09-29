"""An Instagram publication has one launcher, whoever starts it (decision D15 of 2026-09-27).

The publication had no id in the manifest: the desktop bridge, `taktik publish` and the Lab's
publish bench each built `InstagramPostWorkflow` themselves, and the parity gate could not follow
it. It is now `instagram.content.publish`, run by `run_instagram_publish`: the bridge, the
`taktik publish` commands, `taktik workflows run` and the bench call it, and give the same
publication the same workflow, built the same way.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from taktik.core.social_media.instagram.workflows.publish import agent_handler

DEVICE_ID = "emulator-5554"


class _Recorded:
    """The workflow as the launcher builds and runs it."""

    runs: list = []

    def __init__(self, device, device_id, **kwargs):
        self.built = {"device_id": device_id, **{k: v for k, v in kwargs.items() if k not in ("log", "status")}}

    def execute(self, **kwargs):
        _Recorded.runs.append({**self.built, **kwargs})
        return {"success": True, "message": "published", "error_type": None, "confirmed": True}


@pytest.fixture
def recorded(monkeypatch, tmp_path):
    _Recorded.runs = []
    monkeypatch.setitem(agent_handler.run_instagram_publish.__kwdefaults__, "workflow_factory", _Recorded)
    media = []
    for name in ("a.png", "b.png"):
        path = tmp_path / name
        path.write_bytes(b"x")
        media.append(str(path))
    return media


def _bridge(media, monkeypatch):
    import bridges.instagram.publish.bridge as bridge

    class Connection:
        def __init__(self, device_id):
            self.device = object()

        def connect(self):
            return True

        def disconnect(self):
            pass

    monkeypatch.setattr(bridge, "ConnectionService", Connection)
    config = {"deviceId": DEVICE_ID, "postType": "post", "mediaPaths": media, "caption": "hello",
              "hashtags": ["travel"], "packageName": "com.instagram.android"}
    assert bridge.InstagramPublishBridge(config).run() == 0


def _cli(media, monkeypatch):
    from taktik.cli.commands.instagram import publish as publish_cmds

    monkeypatch.setattr(publish_cmds, "_resolve_device", lambda device_id: (object(), DEVICE_ID))
    result = CliRunner().invoke(publish_cmds.publish, ["carousel", *media, "--caption", "hello",
                                                        "--hashtags", "#travel"])
    assert result.exit_code == 0, result.output


def _workflows_run(media, monkeypatch):
    from taktik.cli.commands import workflows as workflow_cmds

    manager = SimpleNamespace(device=object())
    monkeypatch.setattr(workflow_cmds, "_connect", lambda device_id: (manager, DEVICE_ID))
    payload = json.dumps({"postType": "post", "mediaPaths": media, "caption": "hello", "hashtags": ["travel"]})
    result = CliRunner().invoke(workflow_cmds.workflows, ["run", "instagram.content.publish", "-d", DEVICE_ID,
                                                          "--json", payload, "--yes"])
    assert result.exit_code == 0, result.output


def _significant(run):
    return {key: run[key] for key in ("device_id", "post_type", "caption", "hashtags", "media_paths",
                                      "stop_before_share", "story_via_feed")}


def test_the_bridge_and_the_cli_commands_publish_the_same_way(recorded, monkeypatch):
    _bridge(recorded, monkeypatch)
    _cli(recorded, monkeypatch)

    bridge_run, cli_run = _Recorded.runs
    assert _significant(bridge_run) == _significant(cli_run)
    assert bridge_run["post_type"] == "carousel"


def test_workflows_run_reaches_the_same_launcher(recorded, monkeypatch):
    _bridge(recorded, monkeypatch)
    _workflows_run(recorded, monkeypatch)

    bridge_run, cli_run = _Recorded.runs
    assert _significant(bridge_run) == _significant(cli_run)


def test_the_lab_bench_rehearses_through_the_launcher(monkeypatch):
    from bridges.tools.lab.workflow_test.platforms.instagram.workflows import publish

    _Recorded.runs = []
    monkeypatch.setitem(agent_handler.run_instagram_publish.__kwdefaults__, "workflow_factory", _Recorded)
    sent = []
    ipc = SimpleNamespace(send=lambda *args, **kwargs: sent.append((args, kwargs)))

    assert publish.run_instagram_publish(SimpleNamespace(device_id=DEVICE_ID), object(), ipc, "upload_carousel")

    (run,) = _Recorded.runs
    assert run["post_type"] == "carousel" and run["stop_before_share"] is True and len(run["media_paths"]) == 2
