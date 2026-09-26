"""The selector bench tests what production runs on the connected phone.

It used to build its map before connecting, from the baseline; take an override only when its
key was exactly the installed version ("447.0.0.55.81" is not "447.0.0.0"); skip every property
(`_x_base + L(...)`); and evaluate on a raw lxml tree where `//android.widget.X` finds nothing.
Dumps and vocabulary here are invented; no phone is reached.
"""

import functools
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import List

import pytest

from bridges.compat.diagnostics.runtime.selector_test import production
from bridges.compat.diagnostics.runtime.selector_test.production import (
    PlatformCatalogue,
    _TakenScreen,
    is_xpath_selector,
    prepare_selector_test,
    production_device,
    resolve_production_selectors,
)
from bridges.compat.diagnostics.runtime.selector_test.runner import run_selector_tests
from taktik.core.compat.selectors import setup
from taktik.core.shared.ui.language_detection import LanguageDetection

BASELINE = setup.INSTAGRAM_TARGET_VERSION

_STRINGS = {
    "en": {"sample.rows": ['//*[@text="Rows"]']},
    "fr": {"sample.rows": ['//*[@text="Lignes"]']},
}
_LOCALE = {"active": None}


def _set_active_locale(lang):
    _LOCALE["active"] = lang if lang in _STRINGS else None


def _L(key):
    if _LOCALE["active"]:
        return list(_STRINGS[_LOCALE["active"]].get(key, []))
    return [s for table in _STRINGS.values() for s in table.get(key, [])]


@dataclass
class _SampleSelectors:
    _rows_base: List[str] = field(default_factory=lambda: ['//*[@resource-id="com.example.app:id/rows"]'])
    header: List[str] = field(default_factory=lambda: ['//android.widget.TextView[@text="Header"]'])
    next_button: List[str] = field(default_factory=lambda: ['//android.widget.Button[@content-desc="Next"]'])
    labels: List[str] = field(default_factory=lambda: ["Follow", "Suivre"])
    unused: List[str] = field(default_factory=list)

    @property
    def rows(self) -> List[str]:
        return self._rows_base + _L("sample.rows")


_DETECTION = LanguageDetection("Sample", {"Lignes", "Accueil", "Profil", "Suivant"}, {"Rows", "Home", "Profile", "Next"})

_OVERRIDES = """
versions:
  "442.0.0.5":
    sample._rows_base:
      - '//*[@resource-id="rows_v5"]'
  "442.0.0.46":
    sample._rows_base:
      - '//*[@resource-id="rows_v46"]'
  "447.0.0.0":
    sample.header:
      - '//android.widget.TextView[@text="Header 447"]'
"""

_FRENCH_SCREEN = """<hierarchy rotation="0">
  <node class="android.widget.FrameLayout" resource-id="com.example.app:id/root" text="" content-desc="">
    <node class="android.widget.TextView" resource-id="" text="Lignes" content-desc="" />
    <node class="android.widget.TextView" resource-id="" text="Accueil" content-desc="" />
    <node class="android.widget.TextView" resource-id="" text="Profil" content-desc="" />
    <node class="android.widget.TextView" resource-id="" text="Header 447" content-desc="" />
    <node class="android.view.View" resource-id="rows_v46" text="" content-desc="" />
  </node>
</hierarchy>"""


class _Phone:
    """A raw device: the one dump it serves, and a count of what was asked."""

    def __init__(self, xml):
        self.xml = xml
        self.dump_calls = 0
        self.live_xpath_calls = 0

    def dump_hierarchy(self, compressed=False):
        self.dump_calls += 1
        return self.xml

    def xpath(self, selector):
        self.live_xpath_calls += 1
        raise AssertionError("the dump answers; no live xpath")


class _IPC:
    def __init__(self):
        self.messages = []

    def send(self, event_type, **payload):
        self.messages.append((event_type, payload))


@pytest.fixture
def sample(monkeypatch, tmp_path):
    """One invented catalogue behind the REAL patcher, with its own originals and locale."""
    catalogue = _SampleSelectors()
    domains = {"sample": catalogue}
    monkeypatch.setattr(setup, "INSTAGRAM_SELECTOR_DOMAINS", domains)
    monkeypatch.setattr(setup, "_ORIGINALS", {})
    (tmp_path / "instagram.yaml").write_text(_OVERRIDES, encoding="utf-8")
    _set_active_locale(None)
    detections = []

    def detect(screen):
        detections.append(screen)
        barrel = SimpleNamespace(__all__=["SAMPLE_SELECTORS"], SAMPLE_SELECTORS=catalogue)
        return _DETECTION.detect_and_optimize(
            screen, None, barrel=barrel, set_active_locale=_set_active_locale,
            available_locales=lambda: list(_STRINGS),
        )

    yield SimpleNamespace(
        catalogue=catalogue,
        detections=detections,
        platform=PlatformCatalogue(
            domains=domains,
            baseline_version=BASELINE,
            apply_overrides=functools.partial(setup.apply_version_overrides, overrides_dir=str(tmp_path)),
            detect_language=detect,
        ),
    )
    _set_active_locale(None)
    _DETECTION.reset()


def test_every_lower_version_applies_numerically_and_reaches_the_property(sample):
    result = resolve_production_selectors("instagram", "447.0.0.55.81", _TakenScreen(_FRENCH_SCREEN), sample.platform)

    assert result.overrides_applied == 2
    assert result.entries["sample.rows"].xpaths == ['//*[@resource-id="rows_v46"]', '//*[@text="Lignes"]']
    assert result.entries["sample.rows"].source == "yaml"
    assert result.entries["sample.header"].xpaths == ['//android.widget.TextView[@text="Header 447"]']
    assert result.entries["sample.header"].source == "yaml"


def test_a_one_digit_build_below_a_two_digit_one(sample):
    result = resolve_production_selectors("instagram", "442.0.0.10", _TakenScreen(_FRENCH_SCREEN), sample.platform)

    assert result.entries["sample.rows"].xpaths[0] == '//*[@resource-id="rows_v5"]'
    assert result.entries["sample.header"].source == "python"


def test_the_language_is_detected_on_the_tested_screen_after_the_overrides(sample):
    screen = _TakenScreen(_FRENCH_SCREEN)
    result = resolve_production_selectors("instagram", "447.0.0.55.81", screen, sample.platform)

    assert result.language == "fr"
    assert sample.detections == [screen]
    assert '//*[@text="Rows"]' not in result.entries["sample.rows"].xpaths
    # Filtered in place, as production does: nothing left in French.
    assert result.entries["sample.next_button"].xpaths == []
    assert result.entries["sample.next_button"].source == "python"


def test_labels_and_empty_fields_are_counted_not_tested(sample):
    result = resolve_production_selectors("instagram", BASELINE, _TakenScreen(_FRENCH_SCREEN), sample.platform)

    assert "sample.labels" not in result.entries
    assert "sample.unused" not in result.entries
    assert "sample._rows_base" not in result.entries
    assert (result.skipped_not_xpath, result.skipped_empty) == (1, 1)
    assert result.overrides_applied == 0
    assert {entry.source for entry in result.entries.values()} == {"python"}


def test_a_later_run_on_an_older_phone_starts_again_from_the_baseline(sample):
    resolve_production_selectors("instagram", "447.0.0.55.81", _TakenScreen(_FRENCH_SCREEN), sample.platform)
    result = resolve_production_selectors("instagram", BASELINE, _TakenScreen(_FRENCH_SCREEN), sample.platform)

    assert result.entries["sample.rows"].xpaths[0] == '//*[@resource-id="com.example.app:id/rows"]'
    assert result.entries["sample.header"].xpaths == ['//android.widget.TextView[@text="Header"]']


def test_prepare_mounts_the_instagram_proxy_and_reads_one_dump(sample):
    from taktik.core.clone.device.proxy import CloneAwareDeviceProxy

    phone = _Phone(_FRENCH_SCREEN)
    plan = prepare_selector_test(
        "instagram", "", "SAMPLE-SERIAL", phone,
        catalogue=sample.platform, read_installed_version=lambda device_id, app: "447.0.0.55.81",
    )
    results = run_selector_tests(plan.device, plan.selectors.entries, _IPC(), xml=plan.xml, rewrite=plan.rewrite)
    by_action = {item["action"]: item for item in results}

    assert isinstance(plan.device, CloneAwareDeviceProxy)
    assert plan.selectors.version == "447.0.0.55.81"
    assert phone.dump_calls == 1
    assert phone.live_xpath_calls == 0
    assert by_action["sample.rows"]["has_match"] is True
    assert by_action["sample.header"]["has_match"] is True
    assert by_action["sample.next_button"]["has_match"] is False


def test_tiktok_mounts_no_proxy():
    phone = _Phone(_FRENCH_SCREEN)

    assert production_device("tiktok", phone) == (phone, None)


@pytest.mark.parametrize(
    "value, expected",
    [
        ('//android.widget.TextView', True),
        ('(//android.widget.EditText)[1]', True),
        ('@com.example.app:id/title', True),
        ('^Sample.*$', True),
        ('%ample%', True),
        ('Follow', False),
        ('com.example.app:id/title', False),
        ('android.widget.EditText', False),
        ('%', False),
    ],
)
def test_what_production_hands_d_xpath(value, expected):
    assert is_xpath_selector(value) is expected


def test_the_bridge_output_keeps_its_fields(sample, monkeypatch, tmp_path):
    import json

    from bridges.compat.diagnostics.entrypoints import selector_test as bridge

    phone = _Phone(_FRENCH_SCREEN)
    ipc = _IPC()

    class _Connection:
        def __init__(self, device_id):
            self.device = phone

        def connect(self):
            return True

        def disconnect(self):
            phone.disconnected = True

    config = tmp_path / "config.json"
    config.write_text(json.dumps({"device_id": "SAMPLE-SERIAL", "app": "instagram", "version": "447.0.0.55.81"}))
    monkeypatch.setattr(bridge, "IPC", lambda: ipc)
    monkeypatch.setattr(bridge, "ConnectionService", _Connection)
    monkeypatch.setattr(production, "platform_catalogue", lambda app: sample.platform)
    monkeypatch.setattr(bridge.sys, "argv", ["selector_test.py", str(config)])

    with pytest.raises(SystemExit) as exit_info:
        bridge.main()
    assert exit_info.value.code == 0

    results = [payload for kind, payload in ipc.messages if kind == "test_results"]
    assert len(results) == 1
    output = results[0]
    assert set(output) == {
        "app", "version", "device_id", "total_actions", "total_xpaths", "passed", "failed",
        "domain_summary", "results",
        "baseline_version", "overrides_applied", "language", "skipped_not_xpath", "skipped_empty",
    }
    assert output["version"] == "447.0.0.55.81"
    assert output["language"] == "fr"
    assert set(output["results"][0]) == {"action", "domain", "field", "source", "has_match", "xpaths"}
    assert set(output["results"][0]["xpaths"][0]) == {"xpath", "found", "error", "elapsed_ms", "mode"}
    assert ipc.messages[-1][1]["status"] == "some_failed"
    assert phone.disconnected is True


@pytest.fixture
def instagram_back_to_baseline():
    yield
    setup.apply_version_overrides("instagram", setup.INSTAGRAM_TARGET_VERSION)


def test_the_real_447_overrides_reach_the_instagram_property(instagram_back_to_baseline):
    platform = PlatformCatalogue(
        domains=setup.INSTAGRAM_SELECTOR_DOMAINS,
        baseline_version=setup.INSTAGRAM_TARGET_VERSION,
        apply_overrides=setup.apply_version_overrides,
        detect_language=lambda screen: "unknown",
    )

    result = resolve_production_selectors("instagram", "447.0.0.55.81", _TakenScreen(_FRENCH_SCREEN), platform)

    entry = result.entries["detection.business_account_indicators"]
    assert entry.source == "yaml"
    assert "profile.follow_button" in result.entries
    assert not [key for key in result.entries if key.split(".", 1)[1].startswith("_")]


def test_production_catalogue_is_known_for_both_apps():
    assert production.platform_catalogue("instagram").baseline_version == setup.INSTAGRAM_TARGET_VERSION
    assert production.platform_catalogue("tiktok").baseline_version == setup.TIKTOK_TARGET_VERSION
    with pytest.raises(ValueError):
        production.platform_catalogue("unknown-app")
