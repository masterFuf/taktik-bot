"""The schema ownership audit: the numbered list is whole and no DDL lives outside it."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "audits"))

import audit_schema_ownership as audit  # noqa: E402


def _sources(files=None, **changes):
    base = {
        "core/taktik/core/database/local/versions/m0001_baseline.sql": "",
        "core/taktik/core/database/local/migration_steps/x.py": "ALTER TABLE accounts ADD COLUMN a",
        "core/taktik/core/x.py": "nothing",
        "app/electron/database/migrations.ts": "db.exec('CREATE TABLE IF NOT EXISTS app_x (id)')",
        "app/electron/sync/remote/r.ts": "'CREATE TABLE IF NOT EXISTS _sync_meta (key)'",
    }
    base.update(files or {})
    values = dict(files=base, catalog_files=["m0001_baseline.sql"], versions_files=["m0001_baseline.sql"],
                  manifest_committed="{}\n", manifest_built="{}\n")
    values.update(changes)
    return audit.Sources(**values)


def test_the_real_tree_is_clean():
    assert audit.audit(audit.load_sources()) == []


def test_the_self_test_passes():
    assert audit.self_test() == []


def test_a_clean_fake_tree_is_clean():
    assert audit.check_numbered_list(_sources()) == []
    assert audit.check_ddl(_sources(), listed={}) == []


def test_ddl_in_a_bot_repository_is_refused():
    sources = _sources({"core/taktik/core/database/repositories/r.py": "ALTER TABLE accounts ADD COLUMN y"})
    findings = audit.check_ddl(sources, listed={})
    assert len(findings) == 1 and "outside the numbered list" in findings[0]


def test_ddl_in_an_app_service_is_refused():
    sources = _sources({"app/electron/services/s.ts": "db.exec(`CREATE UNIQUE INDEX k ON interactions(x)`)"})
    assert audit.check_ddl(sources, listed={})


def test_lower_case_prose_is_not_ddl():
    sources = _sources({"core/taktik/core/database/local/service.py": '"""Create tables if needed."""'})
    assert audit.check_ddl(sources, listed={}) == []


def test_a_listed_file_may_not_grow_nor_shrink():
    listed = {"app/electron/l.ts": (1, "listed", "test")}
    assert audit.check_ddl(_sources({"app/electron/l.ts": "CREATE INDEX a ON t(c)"}), listed=listed) == []
    grown = audit.check_ddl(_sources({"app/electron/l.ts": "CREATE INDEX a ON t(c); DROP INDEX b"}), listed=listed)
    assert grown and "1 listed" in grown[0]
    shrunk = audit.check_ddl(_sources({"app/electron/l.ts": "nothing"}), listed=listed)
    assert shrunk and shrunk[0].startswith("stale entry")


def test_app_entries_are_not_stale_without_the_app():
    sources = _sources()
    sources.files = {k: v for k, v in sources.files.items() if k.startswith("core/")}
    assert audit.check_ddl(sources, listed={"app/electron/l.ts": (1, "listed", "test")}) == []


def test_a_migration_outside_the_catalog_is_refused():
    sources = _sources(versions_files=["m0001_baseline.sql", "m0002_extra.sql"])
    assert any("m0002_extra.sql" in f for f in audit.check_numbered_list(sources))


def test_an_edited_migration_is_refused():
    sources = _sources(manifest_built='{"changed": true}\n')
    assert any("differs from the catalog" in f for f in audit.check_numbered_list(sources))


def test_a_missing_manifest_is_refused():
    assert audit.check_numbered_list(_sources(manifest_committed=None))
