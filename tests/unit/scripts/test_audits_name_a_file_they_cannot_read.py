"""The coordinate and dry-clamp audits go red, naming the file, when they cannot read one.

Both used to answer "no finding" for a file they could not read or parse, so an unreadable file
passed for a clean one. They now read through `ratchet.read_source` like the other gates.
"""

import sys

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/audits"))

import audit_coordinate_hardcodes as coordinates  # noqa: E402
import audit_no_dry_clamp as dry_clamp  # noqa: E402
from ratchet import UnreadableSource  # noqa: E402

CLEAN = "def f(device, x, y):\n    device.click(x, y)\n"
BROKEN = {
    "not_utf8": b"\xff\xfe\x00 not text",
    "not_python": b"def broken(:\n",
}


@pytest.fixture(params=sorted(BROKEN))
def core_with_a_broken_file(request, tmp_path, monkeypatch):
    root = tmp_path / "core"
    (root / "taktik/core").mkdir(parents=True)
    (root / "bridges").mkdir()
    (root / "taktik/core/fine.py").write_text(CLEAN, encoding="utf-8")
    (root / "taktik/core/broken.py").write_bytes(BROKEN[request.param])
    for audit in (coordinates, dry_clamp):
        monkeypatch.setattr(audit, "ROOT", root)
    return root


@pytest.mark.parametrize("audit", [coordinates, dry_clamp], ids=["coordinates", "dry_clamp"])
def test_collect_refuses_a_file_it_cannot_read(core_with_a_broken_file, audit):
    with pytest.raises(UnreadableSource, match=r"taktik/core/broken\.py"):
        audit.collect()


@pytest.mark.parametrize("audit", [coordinates, dry_clamp], ids=["coordinates", "dry_clamp"])
def test_the_gate_is_red_and_names_the_file(core_with_a_broken_file, audit, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["audit"])
    assert audit.main() == 1
    assert "taktik/core/broken.py" in capsys.readouterr().out
