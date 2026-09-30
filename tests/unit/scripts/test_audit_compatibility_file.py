"""The promotion command the desktop app's exit gate calls: it records a verdict, or refuses and leaves
the registry as it was. The desktop app reads its exit code (`npm run lab:exit -- --promote`)."""

import json
import shutil
import sys

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/audits"))

import audit_compatibility_file as audit  # noqa: E402

REGISTRY = CORE / "taktik/core/compat/data/app_builds.json"


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A copy of the real registry, with one more Instagram build declared under validation."""
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    data["apps"]["instagram"]["builds"].insert(0, {"version": "448.0.0.12.34", "status": "testing"})
    path = tmp_path / "app_builds.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    monkeypatch.setattr(audit, "BUILDS_PATH", path)
    return path


def _verdict(tmp_path, validation):
    path = tmp_path / "verdict.json"
    path.write_text(json.dumps([{"app": "instagram", "version": "448.0.0.12.34", "validation": validation}]),
                    encoding="utf-8")
    return str(path)


def _validation(**changes):
    first = json.loads(REGISTRY.read_text(encoding="utf-8"))["apps"]["instagram"]["builds"][0]["validation"]
    return {**first, **changes}


def test_a_verdict_is_recorded_in_the_registry(tmp_path, registry, capsys):
    assert audit.main(["--promote", _verdict(tmp_path, _validation(date="2026-10-15"))]) == 0
    assert "promoted: instagram 448.0.0.12.34" in capsys.readouterr().out
    build = json.loads(registry.read_text(encoding="utf-8"))["apps"]["instagram"]["builds"][0]
    assert (build["status"], build["validation"]["date"]) == ("validated", "2026-10-15")


def test_a_refused_verdict_leaves_the_registry_untouched(tmp_path, registry, capsys):
    before = registry.read_text(encoding="utf-8")
    assert audit.main(["--promote", _verdict(tmp_path, _validation(runs=[]))]) == 1
    assert "promotion refused, app_builds.json left as it was" in capsys.readouterr().out
    assert registry.read_text(encoding="utf-8") == before

    garbled = tmp_path / "garbled.json"
    shutil.copy(registry, garbled)
    garbled.write_text("[{", encoding="utf-8")
    assert audit.main(["--promote", str(garbled)]) == 1
    assert "is not JSON" in capsys.readouterr().out
    assert registry.read_text(encoding="utf-8") == before
