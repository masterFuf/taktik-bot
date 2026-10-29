"""The audits that read the product's Python go red, naming the file, when they cannot read one.

Several used to answer "no finding" for a file they could not read or parse (the database-singleton
and workflow-callback audits returned an empty list, the screen-test audit counted no screen in a
file it could not parse), read a file that is not UTF-8 with its bytes replaced (the CLI health and
screen-test audits), or stopped on a traceback that did not name it (the bridge events census). They
all read through `ratchet.parse_source`: a file that is not UTF-8, not valid Python or carries a null
byte raises `UnreadableSource` with its path.
"""

import sys

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/audits"))

import audit_bridge_events as bridge_events  # noqa: E402
import audit_cli_health as cli_health  # noqa: E402
import audit_coordinate_hardcodes as coordinates  # noqa: E402
import audit_database_singleton as database_singleton  # noqa: E402
import audit_no_dry_clamp as dry_clamp  # noqa: E402
import audit_screen_test_fixtures as screen_test_fixtures  # noqa: E402
import audit_workflow_callbacks as workflow_callbacks  # noqa: E402
from ratchet import UnreadableSource  # noqa: E402

CLEAN = "def f(device, x, y):\n    device.click(x, y)\n"
BROKEN = {
    "not_utf8": b"\xff\xfe\x00 not text",
    "not_python": b"def broken(:\n",
    "null_byte": b"x = 1\x00\n",
}
# Under the scan of the product audits: the workflow-callback audit reads only the TikTok
# automation bridges.
BROKEN_FILE = "bridges/tiktok/automation/broken.py"

# Each audit: its module, the name of its root constant, how it reads the whole tree, where a
# broken file sits under its scan.
AUDITS = {
    "coordinates": (coordinates, "ROOT", coordinates.collect, BROKEN_FILE),
    "dry_clamp": (dry_clamp, "ROOT", dry_clamp.collect, BROKEN_FILE),
    "database_singleton": (database_singleton, "ROOT", database_singleton.collect, BROKEN_FILE),
    "workflow_callbacks": (workflow_callbacks, "ROOT", workflow_callbacks.collect, BROKEN_FILE),
    "bridge_events": (bridge_events, "ROOT", bridge_events.scan, BROKEN_FILE),
    "cli_health": (cli_health, "ROOT", cli_health.collect, "taktik/cli/broken.py"),
    "screen_test_fixtures": (screen_test_fixtures, "CORE", screen_test_fixtures.read_tree,
                             "tests/unit/broken.py"),
}


@pytest.fixture(params=sorted(BROKEN))
def broken_bytes(request):
    return BROKEN[request.param]


def _core_with_a_broken_file(tmp_path, monkeypatch, name, broken_bytes):
    audit, root_name, _, broken_file = AUDITS[name]
    root = tmp_path / "core"
    for folder in ("taktik/core", "taktik/cli", "bridges/tiktok/automation", "tests/unit"):
        (root / folder).mkdir(parents=True)
    (root / "taktik/core/fine.py").write_text(CLEAN, encoding="utf-8")
    (root / broken_file).write_bytes(broken_bytes)
    monkeypatch.setattr(audit, root_name, root)
    return broken_file


@pytest.mark.parametrize("name", sorted(AUDITS))
def test_reading_the_tree_refuses_a_file_it_cannot_read(tmp_path, monkeypatch, broken_bytes, name):
    broken_file = _core_with_a_broken_file(tmp_path, monkeypatch, name, broken_bytes)
    _, _, read_tree, _ = AUDITS[name]
    with pytest.raises(UnreadableSource, match=broken_file.replace(".", r"\.")):
        read_tree()


@pytest.mark.parametrize("name", sorted(AUDITS))
def test_the_gate_is_red_and_names_the_file(tmp_path, monkeypatch, capsys, broken_bytes, name):
    broken_file = _core_with_a_broken_file(tmp_path, monkeypatch, name, broken_bytes)
    audit = AUDITS[name][0]
    monkeypatch.setattr(sys, "argv", ["audit"])
    assert audit.main() == 1
    assert broken_file in capsys.readouterr().out


def test_the_bridge_events_census_names_the_file_to_the_app_gate(tmp_path, monkeypatch, capsys, broken_bytes):
    """`--json` keeps stdout for the census: the app gate shows stderr when the last line is not JSON."""
    _core_with_a_broken_file(tmp_path, monkeypatch, "bridge_events", broken_bytes)
    assert bridge_events.main(["--json"]) == 1
    captured = capsys.readouterr()
    assert BROKEN_FILE in captured.err
    assert captured.out == ""
