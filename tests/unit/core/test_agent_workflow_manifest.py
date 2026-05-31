from pathlib import Path

from taktik.core.agent import canonical_workflow_id, load_workflow_manifest


def test_agent_workflow_manifest_loads_canonical_ids_from_repo_manifest():
    manifest = load_workflow_manifest()

    assert manifest.contains("instagram.automation.feed")
    assert manifest.contains("tiktok.standalone.upload_post")
    assert manifest.contains("youtube.publish.upload_post")
    assert "feed" in manifest.workflow_types("instagram", "automation")


def test_agent_workflow_manifest_accepts_explicit_path(tmp_path):
    manifest_path = tmp_path / "workflows.manifest.json"
    manifest_path.write_text(
        '{"custom": {"family": ["one", "two"]}}',
        encoding="utf-8",
    )

    manifest = load_workflow_manifest(Path(manifest_path))

    assert tuple(manifest.canonical_ids()) == ("custom.family.one", "custom.family.two")


def test_canonical_workflow_id_is_platform_family_workflow():
    assert canonical_workflow_id("instagram", "automation", "feed") == "instagram.automation.feed"
