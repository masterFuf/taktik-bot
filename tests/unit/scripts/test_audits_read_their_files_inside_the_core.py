"""The dry-clamp and coordinate audits leave out the tests of the core, not the folders above it.

Both read a file's absolute path for `tests` and `test_`: a checkout under a folder named `tests`
(an agent's worktree, `_nuit/agents/tests/taktik-bot/core`) left out every file, the coordinate
audit then said OK on nothing and the dry-clamp audit called its six accepted clamps stale.
"""

import sys

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/audits"))

import audit_coordinate_hardcodes as coordinates  # noqa: E402
import audit_no_dry_clamp as dry_clamp  # noqa: E402

PRODUCT = "import random\n\ndef tap(device, rng):\n    device.click(100, 200)\n    return max(0.1, rng.uniform(0, 1))\n"


@pytest.fixture
def core_under_a_tests_folder(tmp_path, monkeypatch):
    root = tmp_path / "tests" / "core"
    for relative in ("taktik/core/module.py", "bridges/bridge.py", "taktik/core/test_helper.py",
                     "bridges/tests/fixture.py"):
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(PRODUCT, encoding="utf-8")
    for audit in (coordinates, dry_clamp):
        monkeypatch.setattr(audit, "ROOT", root)
    return root


@pytest.mark.parametrize("audit", [coordinates, dry_clamp], ids=["coordinates", "dry_clamp"])
def test_an_audit_reads_the_core_even_under_a_folder_named_tests(core_under_a_tests_folder, audit):
    assert sorted({finding.path for finding in audit.collect()}) == ["bridges/bridge.py", "taktik/core/module.py"]
