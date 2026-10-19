"""DM check bridge: the rule of the DMs written by an AI, run on texts for the app, and through the launcher."""

import json
import os
import subprocess
import sys

import pytest

from bridges.tools.ai_dm import ai_dm_check_bridge
from taktik.core.contract.registry import TOOL_CONTRACTS
from unit.ai_dm_texts import BROKEN_TEXTS, EACH_REASON, FRENCH_ACCOUNT, WITHIN_RULES
from unit.paths import CORE


class FakeIpc:
    def __init__(self):
        self.events = []

    def send(self, msg_type, **kwargs):
        self.events.append({"type": msg_type, **kwargs})

    def error(self, error, error_code=None, **extra):
        self.events.append({"type": "error", "error": error, "error_code": error_code})


def _check(config):
    ipc = FakeIpc()
    code = ai_dm_check_bridge.run(config, ipc=ipc)
    return code, ipc.events


def test_texts_within_the_rule_come_back_without_refusal():
    code, events = _check({"texts": [WITHIN_RULES, WITHIN_RULES], "aiDmRules": FRENCH_ACCOUNT})
    assert code == ai_dm_check_bridge.EXIT_OK
    assert events == [{"type": "ai_dm_check", "checked": 2, "refusals": []}]


@pytest.mark.parametrize("reason, text", EACH_REASON)
def test_each_reason_comes_back_with_the_rank_of_its_text(reason, text):
    code, events = _check({"texts": [WITHIN_RULES, text], "aiDmRules": FRENCH_ACCOUNT})
    assert code == ai_dm_check_bridge.EXIT_OK
    [line] = events
    assert line["type"] == "ai_dm_check" and line["checked"] == 2
    [refusal] = line["refusals"]
    assert refusal["reason"] == reason and refusal["index"] == 2 and refusal["detail"]


def test_every_refused_text_is_said_not_only_the_first():
    texts = [BROKEN_TEXTS["too_short"], WITHIN_RULES, BROKEN_TEXTS["link"]]
    _, [line] = _check({"texts": texts, "aiDmRules": FRENCH_ACCOUNT})
    assert [(r["index"], r["reason"]) for r in line["refusals"]] == [(1, "too_short"), (3, "link")]


def test_a_single_text_keeps_its_rank():
    _, [line] = _check({"texts": [BROKEN_TEXTS["too_long"]], "aiDmRules": FRENCH_ACCOUNT})
    assert line["refusals"][0]["index"] == 1


def test_without_a_frame_the_most_prudent_one_applies():
    """No block: no link, French or English only, like the bot before the phone."""
    _, [line] = _check({"texts": [BROKEN_TEXTS["link"], "Hola Lea, tu panaderia es preciosa, hablamos?"]})
    assert [r["reason"] for r in line["refusals"]] == ["link", "language"]


def test_the_frame_of_the_account_is_the_one_read():
    allowed = {**FRENCH_ACCOUNT, "linksAllowed": True}
    _, [line] = _check({"texts": [BROKEN_TEXTS["link"]], "aiDmRules": allowed})
    assert line["refusals"] == []


@pytest.mark.parametrize("config", [
    pytest.param({}, id="no-texts"),
    pytest.param({"texts": []}, id="empty"),
    pytest.param({"texts": "Bonjour"}, id="not-a-list"),
    pytest.param({"texts": ["Bonjour", 3]}, id="not-a-text"),
    pytest.param({"texts": [WITHIN_RULES], "aiDmRules": "fr"}, id="frame-not-an-object"),
    pytest.param({"texts": [WITHIN_RULES], "aiDmRules": {"forbiddenTerms": "gratuit"}}, id="terms-not-a-list"),
])
def test_a_file_that_is_not_texts_and_a_frame_is_refused_with_its_code(config):
    code, events = _check(config)
    assert code == ai_dm_check_bridge.EXIT_REFUSED
    assert [(e["type"], e["error_code"]) for e in events] == [("error", ai_dm_check_bridge.INPUT_ERROR)]


def test_its_lines_are_declared_to_the_app():
    [contract] = [tool for tool in TOOL_CONTRACTS if tool.bridge == "ai_dm_check_bridge"]
    assert {event.type for event in contract.events} == {"ai_dm_check", "error"}


def test_through_the_launcher_json_lines_only(tmp_path):
    """The way the app runs it: the launcher, the config file as its one argument, one line on stdout."""
    config_path = tmp_path / "ai_dm_check.json"
    config_path.write_text(json.dumps({"texts": [WITHIN_RULES, BROKEN_TEXTS["email"]],
                                       "aiDmRules": FRENCH_ACCOUNT}), encoding="utf-8")
    env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP", "USERPROFILE") if key in os.environ}
    env.update({"PYTHONIOENCODING": "utf-8", "TAKTIK_DB_PATH": str(tmp_path / "taktik-data.db")})
    proc = subprocess.run(
        [sys.executable, str(CORE / "bridges/launcher.py"), "ai_dm_check_bridge", str(config_path)],
        cwd=str(CORE), env=env, capture_output=True, timeout=180,
    )
    lines = [json.loads(line) for line in proc.stdout.decode("utf-8").splitlines() if line.strip()]
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")[-2000:]
    assert lines == [{"type": "ai_dm_check", "checked": 2,
                      "refusals": [{"reason": "email", "detail": "contains an e-mail address", "index": 2}]}]
    assert not (tmp_path / "taktik-data.db").exists()
