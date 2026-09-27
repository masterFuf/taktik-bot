"""The generator of the app's contract types is deterministic, and its audit sees drift.

`scripts/workflow_contract.py` renders the declaration (`taktik/core/app/contract/`) as the
TypeScript the app commits; `scripts/audit_workflow_contract.py` holds the declaration to the
manifests and the events census, and the app's file to the declaration.
"""

import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import audit_workflow_contract as audit  # noqa: E402
import workflow_contract as generator  # noqa: E402
from taktik.core.app import contract as contract_package  # noqa: E402
from taktik.core.app.contract import registry  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def test_the_rendering_is_deterministic_and_says_it_is_generated():
    first, names = generator.render()
    second, _ = generator.render()

    assert first == second
    assert first.startswith("/**\n * GENERATED from the bot - do not edit")
    assert first.endswith("\n") and "\r" not in first
    for name in names:
        assert f" {name}" in first


def test_every_app_setting_is_in_its_settings_type_and_no_other():
    text, _ = generator.render()
    for contract in registry.WORKFLOW_CONTRACTS:
        body = text.split(f"export interface {contract.name}Settings {{", 1)[1].split("\n}", 1)[0]
        keys = {line.strip().split("?")[0].split(":")[0] for line in body.splitlines()
                if line.strip() and not line.strip().startswith("/**")}
        assert keys == {item.key for item in contract.settings if item.app and item.by == "operator"}


def test_check_mode_accepts_the_rendering_and_refuses_a_hand_edit(tmp_path, capsys):
    target = tmp_path / "contract.ts"
    assert generator.main(["--write", str(target)]) == 0
    assert generator.main(["--check", str(target)]) == 0

    target.write_text(target.read_text(encoding="utf-8").replace("max_unfollows?: number", "max_unfollows?: string"),
                      encoding="utf-8")
    assert generator.main(["--check", str(target)]) == 1


def test_the_data_form_lists_what_the_bridge_and_the_launcher_read():
    data = generator.as_data()["workflows"]["tiktok.standalone.tiktok_unfollow"]

    assert ["max_unfollows"] in data["launcherReads"]
    assert ["config", "maxUnfollows"] in data["bridgeReads"]
    assert ["config", "networkReset", "method"] in data["bridgeReads"]
    assert ["device_id"] in data["bridgeReads"]


def test_the_audit_is_green_on_the_declaration(tmp_path):
    assert audit.problems(ROOT, app=tmp_path / "no-app") == []


@pytest.mark.parametrize("change, expected", [
    (lambda c: replace(c, workflow_id="tiktok.standalone.nowhere"), "not a runnable workflow"),
    (lambda c: replace(c, bridge="nowhere_bridge"), "is not in bridges/bridges.manifest.json"),
    (lambda c: replace(c, reader=c.reader + "_gone"), "does not resolve"),
    (lambda c: replace(c, events=(*c.events, replace(c.events[-1], type="never_emitted"))), "emitted nowhere"),
])
def test_the_audit_names_a_declaration_that_drifted(monkeypatch, tmp_path, change, expected):
    drifted = (change(registry.WORKFLOW_CONTRACTS[0]), *registry.WORKFLOW_CONTRACTS[1:])
    monkeypatch.setattr(contract_package, "WORKFLOW_CONTRACTS", drifted)

    found = audit.problems(ROOT, app=tmp_path / "no-app")

    assert any(expected in line for line in found), found


def test_the_audit_refuses_a_stale_app_file(tmp_path):
    app = tmp_path / "app"
    target = app / audit.APP_FILE
    target.parent.mkdir(parents=True)
    target.write_text("// written by hand\n", encoding="utf-8")

    assert any("is not what the bot declares" in line for line in audit.problems(ROOT, app=app))

    text, _ = generator.render()
    target.write_text(text, encoding="utf-8")
    assert audit.problems(ROOT, app=app) == []
