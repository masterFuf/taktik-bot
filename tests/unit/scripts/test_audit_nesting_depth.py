"""The nesting-depth gate reads every engine file, or says which one it could not read."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "audit_nesting_depth.py"


def _gate(monkeypatch, root: Path):
    spec = importlib.util.spec_from_file_location("audit_nesting_depth", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "RACINE", str(root))
    monkeypatch.setattr(module, "TOLERE", {})
    return module


def _deep(levels: int) -> str:
    lines, indent = ["def deep(x):"], "    "
    for _ in range(levels):
        lines.append(f"{indent}if x:")
        indent += "    "
    lines.append(f"{indent}return x")
    return "\n".join(lines) + "\n"


def test_a_file_saved_with_a_bom_is_measured(tmp_path, monkeypatch, capsys):
    engine = tmp_path / "taktik"
    engine.mkdir()
    (engine / "with_bom.py").write_bytes(b"\xef\xbb\xbf" + _deep(10).encode("utf-8"))
    gate = _gate(monkeypatch, tmp_path)

    assert gate.main() == 1
    out = capsys.readouterr().out
    assert "taktik/with_bom.py::deep atteint 10 niveaux" in out
    assert "n'a pas pu etre lu" not in out


def test_an_unreadable_file_turns_the_gate_red(tmp_path, monkeypatch, capsys):
    engine = tmp_path / "taktik"
    engine.mkdir()
    (engine / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    gate = _gate(monkeypatch, tmp_path)

    assert gate.main() == 1
    assert "taktik/broken.py" in capsys.readouterr().out
