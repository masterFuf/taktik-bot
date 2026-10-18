"""The generator of the app's contract types is deterministic, and its audit sees drift.

`scripts/audits/workflow_contract.py` renders the declaration (`taktik/core/contract/`) as the
TypeScript the app commits; `scripts/audits/audit_workflow_contract.py` holds the declaration to the
manifests and the events census, and the app's file to the declaration.
"""

import sys
from dataclasses import replace

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/audits"))

import audit_workflow_contract as audit  # noqa: E402
import workflow_contract as generator  # noqa: E402
from taktik.core import contract as contract_package  # noqa: E402
from taktik.core.contract import registry  # noqa: E402
from taktik.core.contract.schema import (  # noqa: E402
    HOST,
    Bounds,
    Field,
    ListOf,
    OneOf,
    Shape,
    WorkflowContract,
    nested_fields,
)
from workflow_contract import shapes_in  # noqa: E402


def test_the_rendering_is_deterministic_and_says_it_is_generated():
    first, names = generator.render()
    second, _ = generator.render()

    assert first == second
    assert first.startswith("/**\n * GENERATED from the bot - do not edit")
    assert first.endswith("\n") and "\r" not in first
    for name in names:
        assert f" {name}" in first


def test_every_app_setting_is_in_its_settings_type_and_no_other():
    text, _ = generator.render()
    for contract in registry.WORKFLOW_CONTRACTS:
        body = text.split(f"export interface {contract.name}Settings {{", 1)[1].split("\n}", 1)[0]
        keys = {line.strip().split("?")[0].split(":")[0] for line in body.splitlines()
                if line.strip() and not line.strip().startswith("/**")}
        assert keys == {item.key for item in contract.settings if item.app and item.by == "operator"}


def test_check_mode_accepts_the_rendering_and_refuses_a_hand_edit(tmp_path, capsys):
    target = tmp_path / "contract.ts"
    assert generator.main(["--write", str(target)]) == 0
    assert generator.main(["--check", str(target)]) == 0

    target.write_text(target.read_text(encoding="utf-8").replace("max_unfollows?: number", "max_unfollows?: string"),
                      encoding="utf-8")
    assert generator.main(["--check", str(target)]) == 1


def test_the_data_form_lists_what_the_bridge_and_the_launcher_read():
    data = generator.as_data()["workflows"]["tiktok.standalone.tiktok_unfollow"]

    assert ["max_unfollows"] in data["launcherReads"]
    assert ["config", "maxUnfollows"] in data["bridgeReads"]
    assert ["config", "networkReset", "method"] in data["bridgeReads"]
    assert ["device_id"] in data["bridgeReads"]


def test_the_audit_is_green_on_the_declaration(tmp_path):
    assert audit.problems(CORE, app=tmp_path / "no-app") == []


@pytest.mark.parametrize("change, expected", [
    (lambda c: replace(c, workflow_id="tiktok.standalone.nowhere"), "not a runnable workflow"),
    (lambda c: replace(c, bridge="nowhere_bridge"), "is not in bridges/bridges.manifest.json"),
    (lambda c: replace(c, reader=c.reader + "_gone"), "does not resolve"),
    (lambda c: replace(c, events=(*c.events, replace(c.events[-1], type="never_emitted"))), "emitted nowhere"),
])
def test_the_audit_names_a_declaration_that_drifted(monkeypatch, tmp_path, change, expected):
    drifted = (change(registry.WORKFLOW_CONTRACTS[0]), *registry.WORKFLOW_CONTRACTS[1:])
    monkeypatch.setattr(contract_package, "WORKFLOW_CONTRACTS", drifted)

    found = audit.problems(CORE, app=tmp_path / "no-app")

    assert any(expected in line for line in found), found


def test_the_audit_refuses_a_stale_app_file(tmp_path):
    app = tmp_path / "app"
    target = app / audit.APP_FILE
    target.parent.mkdir(parents=True)
    target.write_text("// written by hand\n", encoding="utf-8")

    assert any("is not what the bot declares" in line for line in audit.problems(CORE, app=app))

    text, _ = generator.render()
    target.write_text(text, encoding="utf-8")
    assert audit.problems(CORE, app=app) == []


def test_the_bounds_are_rendered_for_the_app_and_in_the_data_form():
    text, names = generator.render()

    assert "export interface SettingBounds {" in text and "SettingBounds" in names
    assert "INSTAGRAM_AUTOMATION_LIMITS_BOT_BOUNDS" in names
    assert ("  maxProfiles: { minimum: 1, maximum: 500, when: { workflowType: ['target_followers', "
            "'target_following', 'target_profiles', 'hashtags', 'post_url', 'feed'] } },") in text
    assert "  limit: { minimum: 1, maximum: 50, unboundedAt: 0 }," in text
    assert "Conversations to read; 0: all. Default 10. Bounds: 1 to 50, or 0 for no limit." in text
    data = generator.as_data()["workflows"]
    assert data["instagram.engagement.dm_read"]["bounds"] == [
        {"path": ["limit"], "minimum": 1, "maximum": 50, "unboundedAt": 0}]
    assert data["tiktok.standalone.tiktok_unfollow"]["bounds"] == []


def test_every_bounded_setting_the_app_sends_is_in_a_bounds_constant():
    text, _ = generator.render()
    for contract in registry.WORKFLOW_CONTRACTS:
        for path, item, _, _ in nested_fields(contract.settings):
            if item.bounds is not None and item.app:
                assert f"  {item.key}: {generator.ts_bounds(item.bounds)}," in text, ".".join(path)


def test_list_text_and_nested_conditions_render_as_the_app_reads_them():
    inner = Shape(name="ProbeRenderAi", fields=(Field("enabled", "bool", default=False),))
    contract = WorkflowContract(
        workflow_id="probe.render", name="ProbeRender", bridge="probe_bridge", launcher="probe:run",
        reader="probe:read",
        settings=(
            Field("ai", inner, "The AI."),
            Field("names", ListOf("string"), "Names.", bounds=Bounds(min_items=1, max_items=3, max_length=30,
                                                                     when={"ai.enabled": True})),
        ),
    )
    text, names = generator.render((contract,), ())

    assert "export const PROBE_RENDER_BOT_BOUNDS" in text and "PROBE_RENDER_BOT_BOUNDS" in names
    assert "  names: { minItems: 1, maxItems: 3, maxLength: 30, when: { 'ai.enabled': true } }," in text
    assert "Names. Bounds: 1 to 3 items, at most 30 characters when `ai.enabled` is true." in text
    assert generator.as_data((contract,), ())["workflows"]["probe.render"]["bounds"] == [
        {"path": ["names"], "minItems": 1, "maxItems": 3, "maxLength": 30, "when": {"ai.enabled": True}}]


def _declared_keys(text: str, const: str):
    body = text.split(f"export const {const}: BotSettings<", 1)[1].split("\n  fields: {", 1)[1].split("\n  },", 1)[0]
    return {line.strip().split(":", 1)[0] for line in body.splitlines() if line.strip()}


def test_every_member_of_a_settings_type_is_in_its_settings_as_data_and_no_other():
    text, names = generator.render()
    shapes = {}
    for contract in registry.WORKFLOW_CONTRACTS:
        const = f"{generator.constant_name(contract.name)}_BOT_SETTINGS"
        assert const in names
        assert _declared_keys(text, const) == {item.key for item in contract.settings
                                               if item.app and item.by != HOST}
        for item in contract.settings:
            shapes.update({shape.name: shape for shape in shapes_in(item.type)})
    for shape in shapes.values():
        const = f"{generator.constant_name(shape.name)}_BOT_SETTINGS"
        assert _declared_keys(text, const) == {item.key for item in shape.fields if item.app}, shape.name


def test_the_settings_as_data_carry_type_doc_condition_and_who_fills_them():
    text, _ = generator.render()

    assert ("    recipients: { type: { listOf: 'string' }, doc: 'Handles to write to, resolved by the app from "
            "the page\\'s source.', required: true },") in text
    assert "    limits: { type: { shape: INSTAGRAM_AUTOMATION_LIMITS_BOT_SETTINGS }, doc: 'The run\\'s budget.' }," in text
    assert "    feed: { type: { shape: INSTAGRAM_AUTOMATION_FEED_BOT_SETTINGS }, doc: 'The feed walk. Read when " \
           "`workflowType` is \\'feed\\'.', when: { workflowType: 'feed' } }," in text
    assert "    distribution: { type: { oneOf: ['balanced', 'sequential', 'interleaved'] }," in text
    ai = text.split("export const INSTAGRAM_AUTOMATION_AI_BOT_SETTINGS: BotSettings<InstagramAutomationAi> = {", 1)[1]
    assert "openrouterApiKey: { type: 'string'," in ai.split("\n}", 1)[0]
    assert "host: true" in ai.split("openrouterApiKey: ", 1)[1].split("\n", 1)[0]
    cold_dm = text.split("export const INSTAGRAM_COLD_DM_BOT_SETTINGS: ", 1)[1].split("\n}", 1)[0]
    assert "  defaults: INSTAGRAM_COLD_DM_BOT_DEFAULTS,\n  bounds: INSTAGRAM_COLD_DM_BOT_BOUNDS," in cold_dm
    logout = text.split("export const INSTAGRAM_ACCOUNT_LOGOUT_BOT_SETTINGS: ", 1)[1].split("\n}", 1)[0]
    assert "  bounds: {}," in logout


def test_each_declared_workflow_has_its_settings_and_its_value_of_the_selector():
    text, names = generator.render()
    index = text.split("export const WORKFLOW_BOT_SETTINGS: ", 1)[1].split("\n}", 1)[0]
    served = [workflow_id for contract in registry.WORKFLOW_CONTRACTS for workflow_id in contract.serves]

    assert {"DeclaredWorkflowId", "WORKFLOW_BOT_SETTINGS"} <= set(names)
    assert len(served) == len(set(served))
    for workflow_id in served:
        assert f"\n  '{workflow_id}': {{ settings: " in index
    assert ("  'instagram.automation.feed': { settings: INSTAGRAM_AUTOMATION_BOT_SETTINGS, "
            "selector: { key: 'workflowType', value: 'feed' } },") in index
    assert ("  'instagram.scraping.post_url': { settings: INSTAGRAM_SCRAPING_BOT_SETTINGS, "
            "selector: { key: 'type', value: 'post_url' } },") in index
    # One declaration for one workflow: its selector (the notifications' command) stays a setting.
    assert "  'instagram.engagement.notifications': { settings: INSTAGRAM_NOTIFICATIONS_BOT_SETTINGS }," in index
    # Several workflows, no selector: the same file for each.
    assert "  'tiktok.automation.sync_following': { settings: TIKTOK_SYNC_BOT_SETTINGS }," in index


def _family(also, *, selector="mode", values=("a", "b")):
    return WorkflowContract(
        workflow_id="probe.family.a", also=also, selector=selector, name="ProbeFamily", bridge="probe_bridge",
        launcher="probe:run", reader="probe:read",
        settings=(Field("mode", OneOf(values), "The run.", required=True),),
    )


def test_a_workflow_whose_last_segment_is_no_value_of_its_selector_is_refused():
    text, _ = generator.render((_family(("probe.family.b",)),), ())
    assert "  'probe.family.b': { settings: PROBE_FAMILY_BOT_SETTINGS, selector: { key: 'mode', value: 'b' } }," in text

    with pytest.raises(ValueError, match="`c` is no value of the selector `mode`"):
        generator.render((_family(("probe.family.c",)),), ())


def test_a_workflow_served_by_two_declarations_is_refused():
    first = _family(("probe.family.b",))
    second = replace(first, workflow_id="probe.other", also=("probe.family.b",), selector=None, name="ProbeOther")

    with pytest.raises(ValueError, match="probe.family.b is served by two declarations"):
        generator.render((first, second), ())
