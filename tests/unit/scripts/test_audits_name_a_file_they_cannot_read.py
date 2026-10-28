"""The audits that read the product's Python go red, naming the file, when they cannot read one.

Several used to answer "no finding" for a file they could not read or parse (the database-singleton
and workflow-callback audits returned an empty list), or stopped on a traceback that did not name it
(the bridge events census). They all read through `ratchet.parse_source`: a file that is not UTF-8,
not valid Python or carries a null byte raises `UnreadableSource` with its path.
"""

import sys

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/audits"))

import audit_bridge_events as bridge_events  # noqa: E402
import audit_coordinate_hardcodes as coordinates  # noqa: E402
import audit_database_singleton as database_singleton  # noqa: E402
import audit_no_dry_clamp as dry_clamp  # noqa: E402
import audit_workflow_callbacks as workflow_callbacks  # noqa: E402
from ratchet import UnreadableSource  # noqa: E402

CLEAN = "def f(device, x, y):\n    device.click(x, y)\n"
BROKEN = {
    "not_utf8": b"\xff\xfe\x00 not text",
    "not_python": b"def broken(:\n",
    "null_byte": b"x = 1\x00\n",
}
# Under every audit's scan: the workflow-callback audit reads only the TikTok automation bridges.
BROKEN_FILE = "bridges/tiktok/automation/broken.py"

# Each audit and how it reads the whole tree.
AUDITS = {
    "coordinates": (coordinates, coordinates.collect),
    "dry_clamp": (dry_clamp, dry_clamp.collect),
    "database_singleton": (database_singleton, database_singleton.collect),
    "workflow_callbacks": (workflow_callbacks, workflow_callbacks.collect),
    "bridge_events": (bridge_events, bridge_events.scan),
}


@pytest.fixture(params=sorted(BROKEN))
def core_with_a_broken_file(request, tmp_path, monkeypatch):
    root = tmp_path / "core"
    (root / "taktik/core").mkdir(parents=True)
    (root / "bridges/tiktok/automation").mkdir(parents=True)
    (root / "taktik/core/fine.py").write_text(CLEAN, encoding="utf-8")
    (root / BROKEN_FILE).write_bytes(BROKEN[request.param])
    for audit, _ in AUDITS.values():
        monkeypatch.setattr(audit, "ROOT", root)
    return root


@pytest.mark.parametrize("name", sorted(AUDITS))
def test_reading_the_tree_refuses_a_file_it_cannot_read(core_with_a_broken_file, name):
    _, read_tree = AUDITS[name]
    with pytest.raises(UnreadableSource, match=BROKEN_FILE.replace(".", r"\.")):
        read_tree()


@pytest.mark.parametrize("name", sorted(AUDITS))
def test_the_gate_is_red_and_names_the_file(core_with_a_broken_file, name, monkeypatch, capsys):
    audit, _ = AUDITS[name]
    monkeypatch.setattr(sys, "argv", ["audit"])
    assert audit.main() == 1
    assert BROKEN_FILE in capsys.readouterr().out


def test_the_bridge_events_census_names_the_file_to_the_app_gate(core_with_a_broken_file, capsys):
    """`--json` keeps stdout for the census: the app gate shows stderr when the last line is not JSON."""
    assert bridge_events.main(["--json"]) == 1
    captured = capsys.readouterr()
    assert BROKEN_FILE in captured.err
    assert captured.out == ""
