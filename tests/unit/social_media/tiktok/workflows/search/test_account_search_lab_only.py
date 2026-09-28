"""The TikTok account search is the Cartography Lab's alone (decision Q18 of 2026-09-27).

No page and no scheduler node launch it; the CLI is the mirror of the pages, so it has no
workflow id and no CLI command. The launcher it shares with the Hashtag page stays, and the
bridge keeps running `workflowType: search` for the Lab: its recorded run is
`tests/unit/one_path/tiktok_search_bridge_sequence.json` (`search_ai`).
"""

from __future__ import annotations

from click.testing import CliRunner

from taktik.cli.commands.workflows import workflows
from taktik.cli.hosts.registry import build_registry
from taktik.core.agent.io.manifest import load_workflow_manifest
from taktik.core.app.contract.registry import contracts_by_id

SEARCH_ID = "tiktok.automation.search"
HASHTAG_ID = "tiktok.automation.hashtag"


def test_the_manifest_lists_the_hashtag_run_and_not_the_account_search():
    manifest = load_workflow_manifest()

    assert manifest.contains(HASHTAG_ID)
    assert not manifest.contains(SEARCH_ID)


def test_the_cli_registry_has_no_account_search():
    build = build_registry(device=None, device_id="")

    assert HASHTAG_ID in build.workflow_ids
    assert SEARCH_ID not in build.workflow_ids


def test_the_cli_refuses_the_account_search_id():
    result = CliRunner().invoke(workflows, ["run", SEARCH_ID, "--dry-run"])

    assert f"Unknown workflow '{SEARCH_ID}'" in result.output


def test_the_contract_declares_the_hashtag_run_and_keeps_search_for_the_lab():
    declared = contracts_by_id()
    assert SEARCH_ID not in declared
    contract = declared[HASHTAG_ID]
    workflow_type = next(f for f in contract.bridge_fields if f.key == "workflowType")

    assert set(workflow_type.type.values) == {"search", "hashtag"}
