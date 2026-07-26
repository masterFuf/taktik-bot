"""The standalone CLI must reach every workflow the bot can run.

The bot is meant to be usable without the desktop app — the first rule of AGENTS.md. For months
the desktop was the only consumer, so capabilities landed as bridges plus Agent handlers while the
CLI menus stayed put: 40 workflows had a runnable handler and none could be reached from a
terminal by its canonical id. TikTok, Threads, Gmail and YouTube had no CLI surface at all.

These tests pin the mechanism that closes that, and the properties that make it usable in a
script — which is the whole point of standalone.
"""
import json

import pytest
from click.testing import CliRunner

from taktik.cli.commands.workflow_cmds import _coerce, _parse_params, workflows
from taktik.cli.common.registry_builder import build_registry


# --- registry assembly ------------------------------------------------------

def test_every_platform_registers_without_a_device():
    """Handlers take their device by injection, so building the registry must not need a phone."""
    build = build_registry(device=None, device_id="")
    assert build.failures == [], f"registrars failed: {build.failures}"
    assert set(build.platforms) == {"instagram", "tiktok", "threads", "gmail", "youtube"}


def test_the_registry_covers_the_platforms_that_had_no_cli_surface():
    build = build_registry(device=None, device_id="")
    for platform in ("tiktok", "threads", "gmail", "youtube"):
        assert build.ids_for(platform), f"{platform} has no reachable workflow"


def test_workflow_ids_are_canonical_and_namespaced():
    build = build_registry(device=None, device_id="")
    for workflow_id in build.workflow_ids:
        platform, _, rest = workflow_id.partition(".")
        assert platform and rest, workflow_id
        assert workflow_id == workflow_id.lower()


# --- parameter handling -----------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("20", 20),
    ("0.3", 0.3),
    ("true", True),
    ("False", False),
    ("none", None),
    ("hello", "hello"),
    ("a,b,c", ["a", "b", "c"]),
    ('{"k": 1}', {"k": 1}),
])
def test_shell_strings_become_the_types_workflows_expect(raw, expected):
    """`max_profiles=10` must not reach a workflow as the string '10'."""
    assert _coerce(raw) == expected


def test_explicit_params_win_over_the_json_blob():
    params = _parse_params(("max_profiles=5",), json.dumps({"max_profiles": 99, "other": 1}))
    assert params == {"max_profiles": 5, "other": 1}


def test_a_malformed_pair_is_refused_rather_than_ignored():
    from click import BadParameter
    with pytest.raises(BadParameter):
        _parse_params(("no_equals_sign",), None)


def test_a_non_object_json_payload_is_refused():
    from click import BadParameter
    with pytest.raises(BadParameter):
        _parse_params((), "[1, 2, 3]")


# --- command surface --------------------------------------------------------

def test_list_shows_every_workflow():
    result = CliRunner().invoke(workflows, ["list"])
    assert result.exit_code == 0
    build = build_registry(device=None, device_id="")
    for workflow_id in build.workflow_ids:
        assert workflow_id in result.output, workflow_id


def test_list_can_be_filtered_to_one_platform():
    result = CliRunner().invoke(workflows, ["list", "--platform", "tiktok"])
    assert result.exit_code == 0
    assert "tiktok.automation.for_you" in result.output
    assert "instagram.automation.feed" not in result.output


def test_an_unknown_platform_reports_the_known_ones():
    result = CliRunner().invoke(workflows, ["list", "--platform", "myspace"])
    assert result.exit_code == 0
    assert "instagram" in result.output and "tiktok" in result.output


def test_dry_run_resolves_without_touching_a_device():
    result = CliRunner().invoke(
        workflows,
        ["run", "tiktok.automation.for_you", "--dry-run", "--param", "max_videos=20"],
    )
    assert result.exit_code == 0
    assert "resolves" in result.output
    assert '"max_videos": 20' in result.output


def test_an_unknown_workflow_lists_its_platform_siblings():
    """A typo must show what was meant, not just fail."""
    result = CliRunner().invoke(workflows, ["run", "tiktok.automation.for_yu", "--dry-run"])
    assert result.exit_code == 1
    assert "Unknown workflow" in result.output
    assert "tiktok.automation.for_you" in result.output
