"""The registry resolves versions as the patcher does, and can read the catalogue properties.

It took an override only when its key was exactly the installed version, compared versions as
strings ("442.0.0.46" before "442.0.0.5"), and listed fields through `vars()`, which does not see
a property. Versions and selectors here are invented.
"""

from dataclasses import dataclass, field
from typing import List

import pytest

from taktik.core.compat.selectors.registry import (
    VersionedSelectorRegistry,
    build_full_selector_map,
    build_selector_map_from_dataclass,
)

_OVERRIDES = """
versions:
  "442.0.0.5":
    d.rows:
      - '//*[@resource-id="rows_v5"]'
  "442.0.0.46":
    d.rows:
      - '//*[@resource-id="rows_v46"]'
  "447.0.0.0":
    d.header:
      - '//*[@text="Header 447"]'
"""


@pytest.fixture
def registry(tmp_path):
    (tmp_path / "sampleapp.yaml").write_text(_OVERRIDES, encoding="utf-8")
    registry = VersionedSelectorRegistry(overrides_dir=str(tmp_path))
    registry.register_app(
        "sampleapp",
        {"d.rows": ['//*[@resource-id="rows"]'], "d.header": ['//*[@text="Header"]']},
        "410.0.0.53.71",
    )
    return registry


def test_an_installed_build_takes_every_lower_override_version(registry):
    selectors = registry.get_all("sampleapp", "447.0.0.55.81")

    assert selectors["d.rows"].xpaths == ['//*[@resource-id="rows_v46"]']
    assert selectors["d.header"].xpaths == ['//*[@text="Header 447"]']
    assert {entry.source for entry in selectors.values()} == {"yaml"}


def test_versions_compare_numerically(registry):
    assert registry.get("sampleapp", "442.0.0.10", "d.rows").xpaths == ['//*[@resource-id="rows_v5"]']
    assert registry.get("sampleapp", "442.0.0.10", "d.header").source == "python"


def test_the_baseline_reads_the_reference(registry):
    selectors = registry.get_all("sampleapp", "410.0.0.53.71")

    assert selectors["d.rows"].xpaths == ['//*[@resource-id="rows"]']
    assert {entry.source for entry in selectors.values()} == {"python"}


def test_override_versions_are_listed_in_numeric_order(registry):
    assert registry.get_override_versions("sampleapp") == ["442.0.0.5", "442.0.0.46", "447.0.0.0"]


@dataclass
class _Sample:
    _rows_base: List[str] = field(default_factory=lambda: ['//*[@resource-id="rows"]'])
    header: str = '//*[@text="Header"]'
    count: int = 3

    @property
    def rows(self) -> List[str]:
        return self._rows_base + ['//*[@text="Rows"]']

    @property
    def _hidden(self) -> List[str]:
        return ["//hidden"]


def test_properties_are_read_when_asked():
    assert build_selector_map_from_dataclass(_Sample()) == {"header": ['//*[@text="Header"]']}
    assert build_selector_map_from_dataclass(_Sample(), include_properties=True) == {
        "header": ['//*[@text="Header"]'],
        "rows": ['//*[@resource-id="rows"]', '//*[@text="Rows"]'],
    }


def test_a_property_follows_the_active_locale():
    from taktik.core.social_media.instagram.ui.selectors import PROFILE_SELECTORS
    from taktik.core.social_media.instagram.ui.selectors.locales import L, set_active_locale

    try:
        maps = {}
        for lang in ("fr", "en"):
            set_active_locale(lang)
            maps[lang] = build_full_selector_map({"profile": PROFILE_SELECTORS}, include_properties=True)
            fragments = L("profile.follow_button")
            assert fragments and all(f in maps[lang]["profile.follow_button"] for f in fragments)
    finally:
        set_active_locale(None)

    assert maps["fr"]["profile.follow_button"] != maps["en"]["profile.follow_button"]
