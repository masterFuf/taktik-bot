"""Every version override must land on a field that can actually be written.

The locale refactor turned a number of selector lists into computed properties
(``field = _field_base + L("domain.field")``). A property cannot be assigned, so an override
aimed at one is skipped with a warning: it does not break anything visibly, it simply does
NOTHING. That is how the Instagram comment field stayed unreachable from v417 to v442 while
the correct id sat in the YAML the whole time.

These tests read the shipped override files and fail on a key that would be silently dropped.
"""

from pathlib import Path

import pytest
import yaml

from taktik.core.compat.selectors.setup import (
    INSTAGRAM_SELECTOR_DOMAINS,
    TIKTOK_SELECTOR_DOMAINS,
)

DOMAINS = {"instagram": INSTAGRAM_SELECTOR_DOMAINS, "tiktok": TIKTOK_SELECTOR_DOMAINS}
OVERRIDES_DIR = Path(__file__).resolve().parents[3] / "taktik" / "core" / "compat" / "data" / "overrides"


def _override_keys():
    """(app, version, 'domain.field') for every override shipped, all versions."""
    for app in DOMAINS:
        path = OVERRIDES_DIR / f"{app}.yaml"
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for version, overrides in (data.get("versions") or {}).items():
            for key in overrides or {}:
                yield app, str(version), key


def test_override_files_are_present_and_readable():
    keys = list(_override_keys())
    assert keys, f"no override key found under {OVERRIDES_DIR}"


@pytest.mark.parametrize("app,version,key", list(_override_keys()))
def test_override_targets_a_writable_field(app, version, key):
    domain_name, _, field_name = key.partition(".")
    singleton = DOMAINS[app].get(domain_name)
    assert singleton is not None, f"{app} v{version}: unknown domain '{domain_name}' in '{key}'"
    assert hasattr(singleton, field_name), (
        f"{app} v{version}: '{key}' targets no field on {type(singleton).__name__}"
    )
    assert not isinstance(getattr(type(singleton), field_name, None), property), (
        f"{app} v{version}: '{key}' targets a read-only property on "
        f"{type(singleton).__name__} — the override would be silently skipped. "
        f"Target '_{field_name}_base' instead, carrying the baseline entries along."
    )
