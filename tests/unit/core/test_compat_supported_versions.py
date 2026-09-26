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


def _builds_file(tmp_path, instagram_builds):
    data = {
        "architectures": ["arm64-v8a", "x86_64"],
        "apps": {"instagram": {"name": "Instagram", "builds": instagram_builds}},
    }
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
