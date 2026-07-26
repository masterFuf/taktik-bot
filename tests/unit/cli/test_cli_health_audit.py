"""The CLI health audit must catch what months of disuse leave behind.

The CLI went untouched for months while the rest of the bot moved. That produces a specific
failure: a menu branch still calls something that was removed, and nobody notices until a user
picks that entry. Two real instances were found this way:

- `automation._initialize_license_limits(api_key)` — the method had been removed from
  InstagramAutomation, and `api_key` was never defined in that scope either. It raised on every
  automation run started from the terminal.
- `workflow.execute(config)` on DMOutreachWorkflow, which exposes `run()` — and the code then read
  `results[0].success` from what is a dict.

These tests use the audit's own machinery on synthetic modules, so they pin the detection rules
rather than the current state of the tree — which will be clean, and would make an assertion on it
pass for the wrong reason.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "bot" / "scripts" / "audit_cli_health.py"


@pytest.fixture(scope="module")
def audit():
    spec = importlib.util.spec_from_file_location("audit_cli_health", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_cli_health"] = module
    spec.loader.exec_module(module)
    return module


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "probe.py"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_missing_method_is_reported(audit, tmp_path):
    findings = audit.missing_attributes(_write(tmp_path, """
from taktik.core.shared.device.manager import DeviceManager

def go():
    manager = DeviceManager()
    manager.method_that_never_existed()
"""))
    assert len(findings) == 1
    assert "method_that_never_existed" in findings[0]


def test_a_real_method_is_not_reported(audit, tmp_path):
    findings = audit.missing_attributes(_write(tmp_path, """
from taktik.core.shared.device.manager import DeviceManager

def go():
    manager = DeviceManager()
    manager.list_devices()
"""))
    assert findings == []


def test_an_instance_attribute_is_not_reported(audit, tmp_path):
    """`self.device = ...` in __init__ is invisible to hasattr on the class."""
    findings = audit.missing_attributes(_write(tmp_path, """
from taktik.core.shared.device.manager import DeviceManager

def go():
    manager = DeviceManager()
    return manager.device
"""))
    assert findings == []


def test_same_name_in_two_scopes_is_not_confused(audit, tmp_path):
    """A click group and a class instance sharing a name are two different variables.

    This is what made every `@automation.command(...)` look like a call on the
    InstagramAutomation instance built inside the decorated function.
    """
    findings = audit.missing_attributes(_write(tmp_path, """
import click
from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation

@click.group()
def automation():
    pass

@automation.command("run")
def run_it():
    automation = InstagramAutomation(None)
    automation.config = {}
"""))
    assert findings == [], findings


def test_assigning_a_new_attribute_is_allowed(audit, tmp_path):
    """Python lets you attach attributes; only reads and calls can crash."""
    findings = audit.missing_attributes(_write(tmp_path, """
from taktik.core.shared.device.manager import DeviceManager

def go():
    manager = DeviceManager()
    manager.brand_new_attribute = 1
"""))
    assert findings == []


def test_a_file_with_a_bom_is_still_scanned(audit, tmp_path):
    """Several CLI modules start with a BOM; ast.parse rejects it outright."""
    path = tmp_path / "probe.py"
    path.write_text("﻿" + """
from taktik.core.shared.device.manager import DeviceManager

def go():
    manager = DeviceManager()
    manager.gone_missing()
""", encoding="utf-8")
    findings = audit.missing_attributes(path)
    assert len(findings) == 1
    assert "syntax error" not in findings[0]


def test_the_cli_is_currently_clean(audit):
    """Regression guard: both known bugs are fixed and nothing new has appeared."""
    findings = []
    for path in audit.python_files():
        findings.extend(audit.missing_attributes(path))
    assert findings == [], findings
