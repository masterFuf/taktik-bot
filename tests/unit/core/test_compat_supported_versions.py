"""COMPATIBILITY.md is generated from the bot's own sources and cannot drift from them."""

import json

import pytest

from taktik.core.compat.selectors import setup
from taktik.core.compat.selectors.supported_versions import (
    OVERRIDES_DIR,
    CompatibilitySourceError,
    apkmirror_search_url,
    compatibility_file_drift,
    compatibility_rows,
    load_supported_versions,
    render_compatibility_markdown,
    search_query,
    version_family,
)


def _builds_file(tmp_path, instagram_builds, override_status=None):
    instagram = {"name": "Instagram", "builds": instagram_builds}
    if override_status is not None:
        instagram["override_status"] = override_status
    data = {"architectures": ["arm64-v8a", "x86_64"], "apps": {"instagram": instagram}}
    path = tmp_path / "app_builds.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_published_file_matches_its_sources():
    assert compatibility_file_drift() is None


def test_reference_is_the_version_the_patcher_uses():
    supported = load_supported_versions()
    assert supported.app("instagram").reference == setup.INSTAGRAM_TARGET_VERSION
    assert supported.app("tiktok").reference == setup.TIKTOK_TARGET_VERSION


def test_every_download_is_a_mirror_search_never_our_server():
    text = render_compatibility_markdown(load_supported_versions())
    links = [part.split(")")[0] for part in text.split("](")[1:]]
    assert links
    for link in links:
        assert link.startswith("https://www.apkmirror.com")
        assert "taktik" not in link.lower()


def test_rows_list_the_overrides_the_patcher_applies(tmp_path):
    path = _builds_file(tmp_path, [
        {"version": "444.0.0.46.85", "status": "testing"},
        {"version": "410.0.0.53.71", "status": "validated", "recommended": True},
    ])
    rows = {r.version: r for r in compatibility_rows(load_supported_versions(path, OVERRIDES_DIR).app("instagram"))}
    assert rows["410.0.0.53.71"].status == "Reference"
    assert rows["410.0.0.53.71"].overrides_applied == ()
    assert rows["444.0.0.46.85"].status == "Under validation"
    assert "447.0.0.0" not in rows["444.0.0.46.85"].overrides_applied
    assert "442.0.0.0" in rows["444.0.0.46.85"].overrides_applied
    assert rows["447.0.0.0"].display == "447.x"
    assert rows["447.0.0.0"].status == "Supported"


@pytest.mark.parametrize("builds, message", [
    ([{"version": "410.0.0.53.71", "status": "validated"}], "exactly one recommended"),
    ([{"version": "444.0.0.46.85", "status": "testing", "recommended": True}], "not validated"),
    ([
        {"version": "410.0.0.53.71", "status": "validated", "recommended": True},
        {"version": "444.0.0.46.85", "status": "testing"},
    ], "newest first"),
    ([
        {"version": "410.0.0.53.71", "status": "validated", "recommended": True},
        {"version": "410.0.0.53.71", "status": "testing"},
    ], "declared twice"),
    ([{"version": "410.0.0.53.71", "status": "stable", "recommended": True}], "unknown status"),
])
def test_inconsistent_builds_are_refused(tmp_path, builds, message):
    with pytest.raises(CompatibilitySourceError, match=message):
        load_supported_versions(_builds_file(tmp_path, builds), OVERRIDES_DIR)


def test_the_public_file_announces_no_emulator_and_points_to_what_is_tested():
    """Decision of 2026-09-27 (Q10): announce exactly what is tested, say the rest is not. The
    architectures a build is listed for are not tested architectures: only real arm64 phones are,
    and the README's "Tested on" section names them."""
    from taktik.core.compat.selectors.supported_versions import REPO_ROOT

    text = render_compatibility_markdown(load_supported_versions())
    not_tested = "Emulators (`x86_64`, `x86`) are not tested."
    assert not_tested in text
    assert "emulator" not in text.replace(not_tested, "").lower()
    assert "supported on" not in text
    assert 'in the README, section "Tested on"' in text
    assert "\n### Tested on\n" in (REPO_ROOT / "README.md").read_text(encoding="utf-8")


def test_family_keys_and_search_terms():
    assert version_family("447.0.0.0") == "447"
    assert version_family("46.9.3") == "46.9.3"
    assert search_query("447.0.0.0") == "447.0.0"
    assert search_query("410.0.0.53.71") == "410.0.0.53.71"
    assert apkmirror_search_url("TikTok", "46.9.3").endswith("&s=TikTok+46.9.3")


def test_drift_is_reported(tmp_path):
    stale = tmp_path / "COMPATIBILITY.md"
    stale.write_text("# App compatibility\n", encoding="utf-8")
    assert "does not match" in compatibility_file_drift(stale)
    assert "missing" in compatibility_file_drift(tmp_path / "absent.md")


def test_the_json_the_app_reads_carries_the_published_rows(tmp_path):
    """The Lab's exit gate (`npm run lab:exit`) asks for a green run on each version the public
    file lists: it reads the same rows, with their status, never a list of its own."""
    from taktik.core.compat.selectors.supported_versions import as_json

    path = _builds_file(tmp_path, [
        {"version": "444.0.0.46.85", "status": "testing"},
        {"version": "410.0.0.53.71", "status": "validated", "recommended": True},
    ])
    supported = load_supported_versions(path, OVERRIDES_DIR)
    rows = as_json(supported)["apps"]["instagram"]["rows"]
    assert rows == [
        {"version": r.version, "display": r.display, "status": r.status}
        for r in compatibility_rows(supported.app("instagram"))
    ]
    assert {"version": "447.0.0.0", "display": "447.x", "status": "Supported"} in rows
    assert {"version": "444.0.0.46.85", "display": "444.0.0.46.85", "status": "Under validation"} in rows


BUILDS = [
    {"version": "444.0.0.46.85", "status": "testing"},
    {"version": "410.0.0.53.71", "status": "validated", "recommended": True},
]


def test_an_adjusted_version_under_validation_keeps_its_adjustments(tmp_path):
    """Decision of Kevin (2026-09-28): a version the bot adjusts for but no phone of ours runs is
    "Under validation", not "Supported". Its adjustments still apply, to it and to the versions
    above it."""
    path = _builds_file(tmp_path, BUILDS, {"442.0.0.0": "testing"})
    rows = {r.version: r for r in compatibility_rows(load_supported_versions(path, OVERRIDES_DIR).app("instagram"))}
    assert rows["442.0.0.0"].status == "Under validation"
    assert rows["442.0.0.0"].overrides_applied == ("417.0.0.0", "442.0.0.0")
    assert rows["447.0.0.0"].status == "Supported"
    assert "442.0.0.0" in rows["447.0.0.0"].overrides_applied
    assert rows["417.0.0.0"].status == "Supported"


@pytest.mark.parametrize("override_status, message", [
    ({"443.0.0.0": "testing"}, "not a version the bot adjusts for"),
    ({"442.0.0.0": "stable"}, "unknown status"),
])
def test_an_inconsistent_override_status_is_refused(tmp_path, override_status, message):
    with pytest.raises(CompatibilitySourceError, match=message):
        load_supported_versions(_builds_file(tmp_path, BUILDS, override_status), OVERRIDES_DIR)


def test_only_the_versions_our_phones_run_are_announced_supported():
    """Decision 4 of Kevin (2026-09-28): Instagram 442.x and 417.x, TikTok 46.9.3 and 46.6.3, which
    no phone of ours runs, are under validation; 447.x and 47.0.3 (Pixel 6a) stay supported."""
    supported = load_supported_versions()
    status = {(app, r.display): r.status for app in ("instagram", "tiktok")
              for r in compatibility_rows(supported.app(app))}
    assert status[("instagram", "447.x")] == "Supported"
    assert status[("instagram", "442.x")] == "Under validation"
    assert status[("instagram", "417.x")] == "Under validation"
    assert status[("tiktok", "47.0.3")] == "Supported"
    assert status[("tiktok", "46.9.3")] == "Under validation"
    assert status[("tiktok", "46.6.3")] == "Under validation"


def test_the_json_carries_the_status_of_each_adjusted_version(tmp_path):
    """The desktop app shows a phone on an adjusted version under validation as under validation,
    from this very status (`npm run appversions:adjusted`)."""
    from taktik.core.compat.selectors.supported_versions import as_json

    path = _builds_file(tmp_path, BUILDS, {"442.0.0.0": "testing"})
    app = as_json(load_supported_versions(path, OVERRIDES_DIR))["apps"]["instagram"]
    assert app["override_status"] == {"417.0.0.0": "validated", "442.0.0.0": "testing", "447.0.0.0": "validated"}
