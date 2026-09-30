"""COMPATIBILITY.md is generated from the bot's own sources and cannot drift from them."""

import copy
import json

import pytest

import taktik.core.compat.selectors.supported_versions as supported_versions
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


def _validation(abi="arm64-v8a", **changes):
    """A well-formed validation block: what a promotion records for a validated build."""
    block = {
        "date": "2026-09-30",
        "core_commit": "5" * 40,
        "decided_by": "maintainer",
        "runs": [{
            "device": "Pixel 6a",
            "version_code": 385311922,
            "abi": abi,
            "language": "fr",
            "report_sha256": "a" * 64,
            "core_commit": "4" * 40,
        }],
        "notes": {"fr": "Aucune limite connue.", "en": "No known limit."},
    }
    block.update(changes)
    return block


def _build(version, status="validated", recommended=False, abi="arm64-v8a"):
    entry = {"version": version, "status": status}
    if recommended:
        entry["recommended"] = True
    if status == "validated":
        entry["validation"] = _validation(abi)
    return entry


# The adjustments no phone of ours runs, as the registry declares them since 2026-09-30.
ADJUSTED_ONLY = {"442.0.0.0": "adjusted", "417.0.0.0": "adjusted"}
# The same, in the words of 2026-09-28: the rules on the evidence are tested with them, so that the
# reader of before is seen accepting what it had to refuse, not tripping on a new word.
UNDER_VALIDATION = {"442.0.0.0": "testing", "417.0.0.0": "testing"}
BUILDS = [_build("447.0.0.55.81"), _build("410.0.0.53.71", recommended=True)]


def _builds_file(tmp_path, instagram_builds, override_status=ADJUSTED_ONLY, architectures=("arm64-v8a",)):
    instagram = {"name": "Instagram", "builds": instagram_builds}
    if override_status is not None:
        instagram["override_status"] = override_status
    data = {"architectures": list(architectures), "apps": {"instagram": instagram}}
    path = tmp_path / "app_builds.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _rows(path):
    return {r.version: r for r in compatibility_rows(load_supported_versions(path, OVERRIDES_DIR).app("instagram"))}


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
    rows = _rows(_builds_file(tmp_path, [_build("444.0.0.46.85", status="testing"), *BUILDS[1:]],
                              override_status={**ADJUSTED_ONLY, "447.0.0.0": "testing"}))
    assert rows["410.0.0.53.71"].status == "Reference"
    assert rows["410.0.0.53.71"].overrides_applied == ()
    assert rows["444.0.0.46.85"].status == "Under validation"
    assert "447.0.0.0" not in rows["444.0.0.46.85"].overrides_applied
    assert "442.0.0.0" in rows["444.0.0.46.85"].overrides_applied
    assert rows["447.0.0.0"].display == "447.x"
    assert rows["447.0.0.0"].status == "Under validation"


@pytest.mark.parametrize("builds, message", [
    ([{**_build("410.0.0.53.71")}], "exactly one recommended"),
    ([_build("444.0.0.46.85", status="testing", recommended=True)], "not validated"),
    ([
        _build("410.0.0.53.71", recommended=True),
        _build("444.0.0.46.85", status="testing"),
    ], "newest first"),
    ([
        _build("410.0.0.53.71", recommended=True),
        _build("410.0.0.53.71", status="testing"),
    ], "declared twice"),
    ([{"version": "410.0.0.53.71", "status": "stable", "recommended": True}], "unknown status"),
])
def test_inconsistent_builds_are_refused(tmp_path, builds, message):
    with pytest.raises(CompatibilitySourceError, match=message):
        load_supported_versions(_builds_file(tmp_path, builds, override_status={**ADJUSTED_ONLY, "447.0.0.0": "testing"}),
                                OVERRIDES_DIR)


def test_a_validated_build_without_its_evidence_is_refused(tmp_path):
    """A build announced validated says which runs of the Lab prove it (2026-09-30). The reader refused
    a second recommended build; it accepted a validated one with nothing behind it."""
    bare = {"version": "410.0.0.53.71", "status": "validated", "recommended": True}
    with pytest.raises(CompatibilitySourceError, match="410.0.0.53.71 is validated without its validation block"):
        load_supported_versions(_builds_file(tmp_path, [BUILDS[0], bare], UNDER_VALIDATION), OVERRIDES_DIR)


def test_a_build_under_validation_carries_no_validation_block(tmp_path):
    testing = {**_build("444.0.0.46.85", status="testing"), "validation": _validation()}
    with pytest.raises(CompatibilitySourceError, match="444.0.0.46.85 carries a validation block but is testing"):
        load_supported_versions(_builds_file(tmp_path, [BUILDS[0], testing, BUILDS[1]], UNDER_VALIDATION), OVERRIDES_DIR)


def _run(**changes):
    run = copy.deepcopy(_validation()["runs"][0])
    run.update(changes)
    return run


@pytest.mark.parametrize("block, message", [
    (_validation(date="30/09/2026"), "date"),
    (_validation(core_commit="5" * 12), "core_commit"),
    (_validation(decided_by=" "), "decided_by"),
    (_validation(runs=[]), "runs"),
    (_validation(runs=[_run(version_code="385311922")]), "version_code"),
    (_validation(runs=[_run(version_code=True)]), "version_code"),
    (_validation(runs=[_run(report_sha256="A" * 64)]), "report_sha256"),
    (_validation(runs=[_run(core_commit=None)]), "core_commit"),
    (_validation(runs=[_run(device="")]), "device"),
    (_validation(runs=[_run(language="french")]), "language"),
    (_validation(runs=[_run(abi="arm64")]), "abi"),
    (_validation(runs=[_run(abi="armeabi-v7a")]), "not an announced architecture"),
    (_validation(runs=[_run(serial="X")]), "unknown key"),
    (_validation(runs=[_run(exception={"reason": "a client account"})]), "skipped_actions"),
    (_validation(runs=[_run(exception={"reason": "", "skipped_actions": ["dm.open_thread"]})]), "reason"),
    (_validation(notes={"fr": "Aucune limite connue."}), "notes"),
    (_validation(verdict="green"), "unknown key"),
])
def test_a_malformed_validation_block_is_refused(tmp_path, block, message):
    build = {**_build("447.0.0.55.81"), "validation": block}
    with pytest.raises(CompatibilitySourceError, match=message):
        load_supported_versions(_builds_file(tmp_path, [build, BUILDS[1]], UNDER_VALIDATION), OVERRIDES_DIR)


def test_a_run_under_a_declared_exception_is_read_with_it(tmp_path):
    exception = {"reason": "account of a client", "skipped_actions": ["dm.open_thread", "story.open_from_tray"]}
    build = {**_build("447.0.0.55.81"), "validation": _validation(runs=[_run(exception=exception)])}
    supported = load_supported_versions(_builds_file(tmp_path, [build, BUILDS[1]]), OVERRIDES_DIR)
    run = supported.app("instagram").builds[0].validation.runs[0]
    assert run.exception.skipped_actions == ("dm.open_thread", "story.open_from_tray")
    assert run.exception.reason == "account of a client"


def test_an_announced_architecture_no_validated_run_played_is_refused(tmp_path):
    """No x86 build exists in our store and no phone of ours runs one (2026-09-30): an architecture is
    announced only when a validated run played a build of it."""
    with pytest.raises(CompatibilitySourceError, match="x86_64 is announced but no validated run played it"):
        load_supported_versions(_builds_file(tmp_path, BUILDS, UNDER_VALIDATION, architectures=("arm64-v8a", "x86_64")),
                                OVERRIDES_DIR)
    with pytest.raises(CompatibilitySourceError, match="riscv64 is not an Android ABI"):
        load_supported_versions(_builds_file(tmp_path, BUILDS, UNDER_VALIDATION, architectures=("arm64-v8a", "riscv64")),
                                OVERRIDES_DIR)


def test_the_architectures_are_those_of_the_validated_runs():
    supported = load_supported_versions()
    played = {run.abi for support in supported.apps for build in support.builds if build.validation
              for run in build.validation.runs}
    assert supported.architectures == ("arm64-v8a", "armeabi-v7a")
    assert played == set(supported.architectures)


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

    path = _builds_file(tmp_path, BUILDS)
    supported = load_supported_versions(path, OVERRIDES_DIR)
    rows = as_json(supported)["apps"]["instagram"]["rows"]
    assert rows == [
        {"version": r.version, "display": r.display, "status": r.status}
        for r in compatibility_rows(supported.app("instagram"))
    ]
    assert {"version": "447.0.0.0", "display": "447.x", "status": "Supported"} in rows
    assert {"version": "447.0.0.55.81", "display": "447.0.0.55.81", "status": "Validated"} in rows
    assert {"version": "442.0.0.0", "display": "442.x", "status": "Adjusted, not validated"} in rows


def test_an_adjusted_version_under_validation_keeps_its_adjustments(tmp_path):
    """A version the bot adjusts for but no phone of ours runs is not "Supported" (2026-09-28). Its
    adjustments still apply, to it and to the versions above it."""
    rows = _rows(_builds_file(tmp_path, BUILDS, {"442.0.0.0": "testing", "417.0.0.0": "adjusted"}))
    assert rows["442.0.0.0"].status == "Under validation"
    assert rows["442.0.0.0"].overrides_applied == ("417.0.0.0", "442.0.0.0")
    assert rows["447.0.0.0"].status == "Supported"
    assert "442.0.0.0" in rows["447.0.0.0"].overrides_applied
    assert rows["417.0.0.0"].status == "Adjusted, not validated"


def test_an_adjusted_version_nobody_will_validate_says_so(tmp_path):
    """Two versions per app (2026-09-30): the adjustments kept for other versions are not "Under
    validation", since none of them will be validated. They say what they are, and still apply."""
    rows = _rows(_builds_file(tmp_path, BUILDS))
    assert rows["442.0.0.0"].status == "Adjusted, not validated"
    assert rows["417.0.0.0"].status == "Adjusted, not validated"
    assert rows["442.0.0.0"].overrides_applied == ("417.0.0.0", "442.0.0.0")
    assert rows["442.0.0.0"].desktop_app == "-"


def test_adjustments_announced_validated_need_a_validated_build_of_their_version(tmp_path):
    """"Supported" is proven by the validated build of that version, which carries the runs: a key
    left at its default (validated) with no such build is refused."""
    with pytest.raises(CompatibilitySourceError, match=r"447\.x .* no validated build of that version"):
        load_supported_versions(_builds_file(tmp_path, [BUILDS[1]], UNDER_VALIDATION), OVERRIDES_DIR)


@pytest.mark.parametrize("override_status, message", [
    ({"443.0.0.0": "testing"}, "not a version the bot adjusts for"),
    ({"442.0.0.0": "stable"}, "unknown status"),
])
def test_an_inconsistent_override_status_is_refused(tmp_path, override_status, message):
    with pytest.raises(CompatibilitySourceError, match=message):
        load_supported_versions(_builds_file(tmp_path, BUILDS, override_status), OVERRIDES_DIR)


def test_the_registry_offers_two_versions_per_app():
    """The maintainer's decision of 2026-09-30: Instagram 410.0.0.53.71 (installed by default) and
    447.0.0.55.81, TikTok 43.1.4 (installed by default) and 47.0.3, each validated with the Lab runs
    that prove it. Instagram 444 and TikTok 46.6.3 leave the builds; the adjustments kept for 442.x,
    417.x, 46.9.3 and 46.6.3 are announced for what they are."""
    supported = load_supported_versions()
    builds = {app: [(b.version, b.status, b.recommended) for b in supported.app(app).builds]
              for app in ("instagram", "tiktok")}
    assert builds == {
        "instagram": [("447.0.0.55.81", "validated", False), ("410.0.0.53.71", "validated", True)],
        "tiktok": [("47.0.3", "validated", False), ("43.1.4", "validated", True)],
    }
    status = {(app, r.display): r.status for app in ("instagram", "tiktok")
              for r in compatibility_rows(supported.app(app))}
    assert status[("instagram", "447.x")] == "Supported"
    assert status[("instagram", "447.0.0.55.81")] == "Validated"
    assert status[("instagram", "442.x")] == "Adjusted, not validated"
    assert status[("instagram", "417.x")] == "Adjusted, not validated"
    assert status[("tiktok", "47.0.3")] == "Validated"
    assert status[("tiktok", "46.9.3")] == "Adjusted, not validated"
    assert status[("tiktok", "46.6.3")] == "Adjusted, not validated"
    assert "Under validation" not in status.values()


def test_each_validation_cites_runs_without_naming_a_phone_or_an_account():
    """The core is public: a run names the phone's model, never its serial; the report it fingerprints
    stays on the maintainer's machine."""
    supported = load_supported_versions()
    for support in supported.apps:
        for build in support.builds:
            assert build.validation is not None, build.version
            assert build.validation.runs, build.version
            for run in build.validation.runs:
                assert run.device.startswith("Pixel "), run.device
                assert len(run.report_sha256) == 64


def test_the_json_carries_the_status_of_each_adjusted_version(tmp_path):
    """The desktop app reads the status of each adjusted version from the bot
    (`npm run appversions:adjusted`)."""
    from taktik.core.compat.selectors.supported_versions import as_json

    app = as_json(load_supported_versions(_builds_file(tmp_path, BUILDS), OVERRIDES_DIR))["apps"]["instagram"]
    assert app["override_status"] == {"417.0.0.0": "adjusted", "442.0.0.0": "adjusted", "447.0.0.0": "validated"}


def test_the_public_file_shows_the_evidence_and_the_limits_of_each_validated_build(tmp_path):
    text = render_compatibility_markdown(load_supported_versions(_builds_file(tmp_path, BUILDS), OVERRIDES_DIR))
    assert "- `447.0.0.55.81`, validated on 2026-09-30: 1 Lab run on Pixel 6a (arm64-v8a, versionCode 385311922, fr)." in text
    assert "Notes: No known limit." in text
    assert "**Adjusted, not validated**" in text


# ─── Promotion: the bot records the verdict the Lab's exit gate hands it ─────────


def _raw(tmp_path, builds):
    return json.loads(_builds_file(tmp_path, builds).read_text(encoding="utf-8"))


def test_a_promotion_records_the_verdict_and_leaves_a_readable_file(tmp_path):
    raw = _raw(tmp_path, [_build("448.0.0.12.34", status="testing"), *BUILDS])
    block = _validation(notes={"fr": "Rien à signaler.", "en": "Nothing to report."})
    promoted = supported_versions.promote_builds(raw, [{"app": "instagram", "version": "448.0.0.12.34", "validation": block}])

    newest = promoted["apps"]["instagram"]["builds"][0]
    assert newest == {"version": "448.0.0.12.34", "status": "validated", "validation": block}
    assert raw["apps"]["instagram"]["builds"][0]["status"] == "testing"  # the input is left as it was
    path = tmp_path / "promoted.json"
    path.write_text(supported_versions.render_builds_json(promoted), encoding="utf-8")
    build = load_supported_versions(path, OVERRIDES_DIR).app("instagram").builds[0]
    assert (build.version, build.status, build.validation.notes["en"]) == ("448.0.0.12.34", "validated", "Nothing to report.")


def test_a_promotion_replaces_the_evidence_of_a_build_already_validated(tmp_path):
    raw = _raw(tmp_path, BUILDS)
    block = _validation(date="2026-10-15")
    promoted = supported_versions.promote_builds(raw, [{"app": "instagram", "version": "410.0.0.53.71", "validation": block}])
    assert promoted["apps"]["instagram"]["builds"][1] == {**_build("410.0.0.53.71", recommended=True), "validation": block}


@pytest.mark.parametrize("promotion, message", [
    ({"app": "instagram", "version": "448.0.0.12.34", "validation": _validation()}, "448.0.0.12.34 is not a declared build"),
    ({"app": "youtube", "version": "1.0", "validation": _validation()}, "youtube is not an app of app_builds.json"),
    ({"app": "instagram", "version": "447.0.0.55.81"}, "a validation block"),
    ({"app": "instagram", "version": "447.0.0.55.81", "validation": _validation(), "recommended": True}, "unknown key"),
])
def test_a_promotion_that_names_nothing_declared_is_refused(tmp_path, promotion, message):
    with pytest.raises(CompatibilitySourceError, match=message):
        supported_versions.promote_builds(_raw(tmp_path, BUILDS), [promotion])


def test_a_promotion_is_written_only_when_the_whole_file_stays_valid(tmp_path):
    path = _builds_file(tmp_path, [_build("448.0.0.12.34", status="testing"), *BUILDS])
    before = path.read_text(encoding="utf-8")
    verdict = tmp_path / "verdict.json"
    verdict.write_text(json.dumps([{"app": "instagram", "version": "448.0.0.12.34",
                                    "validation": _validation(runs=[_run(abi="x86")])}]), encoding="utf-8")
    with pytest.raises(CompatibilitySourceError, match="abi"):
        supported_versions.promote_file(verdict, path, OVERRIDES_DIR)
    assert path.read_text(encoding="utf-8") == before

    verdict.write_text(json.dumps([{"app": "instagram", "version": "448.0.0.12.34", "validation": _validation()}]),
                       encoding="utf-8")
    promoted = supported_versions.promote_file(verdict, path, OVERRIDES_DIR)
    assert promoted == [("instagram", "448.0.0.12.34")]
    assert path.read_text(encoding="utf-8") == supported_versions.render_builds_json(json.loads(path.read_text(encoding="utf-8")))
    assert load_supported_versions(path, OVERRIDES_DIR).app("instagram").builds[0].status == "validated"


def test_the_registry_is_written_as_the_promotion_writes_it():
    """The file is rewritten whole by each promotion: kept in that very format, a promotion changes
    only the lines of the build it promotes."""
    text = supported_versions.BUILDS_PATH.read_text(encoding="utf-8")
    assert text == supported_versions.render_builds_json(json.loads(text))
