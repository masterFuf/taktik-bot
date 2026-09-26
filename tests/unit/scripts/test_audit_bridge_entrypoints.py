"""The bridge entry audit: every bridge on `run_bridge_main`, one config source, lists = manifest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import audit_bridge_entrypoints as audit  # noqa: E402

MANIFEST = {"tiktok": {"x_bridge": "bridges.tiktok.x"}, "database": {"schema_bridge": "bridges.database.schema"}}
GOOD_ENTRY = (
    "from bridges.common.runtime.entrypoint import run_bridge_main\n\n"
    "def main():\n    run_bridge_main(Bridge, usage='x_bridge <config_path>')\n"
)
APP_PATHS = (
    "export const PLATFORM_BRIDGES = {\n  tiktok: [\n    'x_bridge',\n  ],\n  database: [\n    'schema_bridge',\n  ],\n"
    "} as const\n"
)


def _sources(**files):
    bridge_files = {"bridges/tiktok/x.py": GOOD_ENTRY, "bridges/database/schema.py": GOOD_ENTRY}
    bridge_files.update({key.replace("__", "/") + ".py": text for key, text in files.items()})
    return audit.Sources(
        manifest=MANIFEST,
        bridge_files=bridge_files,
        build_files={"core/scripts/build_exe.py": "json.loads(Path('bridges.manifest.json').read_text())"},
        app_paths=APP_PATHS,
    )


def test_the_real_tree_is_clean():
    assert audit.audit(audit.load_sources()) == []


def test_a_clean_fake_tree_is_clean():
    assert audit.audit(_sources()) == []


def test_a_main_of_its_own_is_refused():
    findings = audit.audit(_sources(bridges__tiktok__x="import sys\n\ndef main():\n    run(sys.argv[1])\n"))
    assert any("does not call run_bridge_main" in f for f in findings)
    assert any("reads sys.argv" in f for f in findings)


def test_the_stdin_source_is_refused():
    entry = "def main():\n    run_bridge_main(Bridge, config_source='stdin')\n"
    helper = "def run_bridge_main(factory, *, config_source='argv'):\n    pass\n"
    findings = audit.audit(_sources(bridges__tiktok__x=entry, bridges__common__runtime__entrypoint=helper))
    assert any("picks another config source" in f for f in findings)
    assert any("accepts another config source" in f for f in findings)


def test_flags_parsed_by_a_bridge_are_refused():
    findings = audit.audit(_sources(bridges__database__schema="import argparse\n" + GOOD_ENTRY))
    assert any("imports argparse" in f for f in findings)


def test_a_config_loader_reading_argv_outside_the_entrypoint_is_refused():
    loader = "import sys\n\ndef load():\n    return open(sys.argv[1]).read()\n"
    findings = audit.audit(_sources(bridges__tiktok__runtime__commands=loader))
    assert findings == ["bridges/tiktok/runtime/commands.py:4 reads sys.argv (only run_bridge_main reads the config)"]


def test_a_build_list_written_by_hand_is_refused():
    sources = _sources()
    sources.build_files["core/taktik_launcher.spec"] = "hiddenimports = ['bridges.tiktok.x']\n"
    findings = audit.audit(sources)
    assert "core/taktik_launcher.spec does not read bridges.manifest.json" in findings
    assert any("names bridges by hand: ['bridges.tiktok.x']" in f for f in findings)


def test_the_app_list_is_compared_platform_by_platform():
    sources = _sources()
    sources.app_paths = APP_PATHS.replace("'x_bridge',\n  ],\n  database: [\n", "],\n  database: [\n    'x_bridge',\n")
    findings = audit.audit(sources)
    assert "paths.ts, tiktok: missing ['x_bridge']" in findings
    assert "paths.ts, database: extra ['x_bridge']" in findings
