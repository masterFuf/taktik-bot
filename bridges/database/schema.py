"""Schema bridge: report, or bring the local database to, the schema version of this build.

    schema_bridge <config.json>

    {"command": "status" | "migrate", "db"?: PATH, "backupDir"?: PATH, "afterLegacyApp"?: bool}

`backupDir` and `afterLegacyApp` apply to `migrate`. `afterLegacyApp` says the 1.9.8 app has just
migrated the base: only then may the bot's own old steps run on a base that is not the 1.9.8
schema.

`status` never writes, not even the -wal/-shm side files of a closed base. Events are JSON lines
on stdout: `schema_status`, `schema_progress`, `schema_result`, and `error` with an
`error_code`. Logs go to stderr.

The base is `db`, else TAKTIK_DB_PATH, else the standalone default. When both `db` and
TAKTIK_DB_PATH are given they must name the same file.
"""

from __future__ import annotations

import os
from typing import List, Optional

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_REFUSED = 2
EXIT_NEEDS_LEGACY_APP = 3

MAX_DIFFERENCES = 50


class DbPathMismatch(ValueError):
    pass


def _same_file(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def resolve_db_path(cli_path: Optional[str], env: Optional[dict] = None) -> str:
    env = os.environ if env is None else env
    env_path = env.get("TAKTIK_DB_PATH")
    if cli_path and env_path and not _same_file(cli_path, env_path):
        raise DbPathMismatch(f"db {cli_path} and TAKTIK_DB_PATH {env_path} name different files")
    if cli_path:
        return cli_path
    if env_path:
        return env_path
    from taktik.core.database.local.paths import get_default_database_path

    return get_default_database_path()


def _trim(differences: List[str]) -> dict:
    return {"differences": differences[:MAX_DIFFERENCES], "difference_count": len(differences)}


USAGE = 'schema_bridge <config.json>: {"command": "status"|"migrate", "db"?, "backupDir"?, "afterLegacyApp"?}'
COMMANDS = ("status", "migrate")


def _default_ipc():
    from bridges.common.runtime.ipc import IPC

    return IPC()


def run(config: dict, ipc=None) -> int:
    if ipc is None:
        ipc = _default_ipc()

    command = config.get("command")
    if command not in COMMANDS:
        ipc.error(f"usage: {USAGE}", error_code="SCHEMA_USAGE")
        return EXIT_FAILED

    try:
        db_path = resolve_db_path(config.get("db"))
    except DbPathMismatch as exc:
        ipc.error(str(exc), error_code="SCHEMA_DB_PATH_MISMATCH")
        return EXIT_REFUSED

    from taktik.core.database.local.versions import TOO_NEW, inspect_database, migrate_database

    status = inspect_database(db_path)
    status_payload = status.to_dict()
    status_payload.update(_trim(status.differences))
    ipc.send("schema_status", status=status_payload)
    if command == "status":
        return EXIT_REFUSED if status.state == TOO_NEW else EXIT_OK

    def progress(step: str, message: str = "") -> None:
        ipc.send("schema_progress", step=step, message=message)

    result = migrate_database(
        db_path,
        backup_dir=config.get("backupDir"),
        applied_by="schema_bridge",
        on_progress=progress,
        legacy_app_done=bool(config.get("afterLegacyApp")),
    )
    payload = result.to_dict()
    payload.update(_trim(result.differences))
    if payload.get("backup"):
        payload["backup"].pop("row_counts", None)
    ipc.send("schema_result", **payload)
    if result.success:
        return EXIT_OK
    if result.action == "needs_legacy_app":
        return EXIT_NEEDS_LEGACY_APP
    if result.action == "refused":
        ipc.error(result.message, error_code="SCHEMA_REFUSED")
        return EXIT_REFUSED
    ipc.error(result.message, error_code="SCHEMA_MIGRATION_FAILED")
    return EXIT_FAILED


class SchemaRun:
    """One schema command, from its config file (read by `run_bridge_main`)."""

    def __init__(self, config: dict, ipc=None):
        self.config = config
        self.ipc = ipc

    def run(self) -> int:
        return run(self.config, ipc=self.ipc)


def main() -> None:
    from bridges.common.runtime.entrypoint import run_bridge_main

    ipc = _default_ipc()
    run_bridge_main(lambda config: SchemaRun(config, ipc), usage=USAGE,
                    report_error=lambda message, _reason: ipc.error(message, error_code="SCHEMA_USAGE"),
                    catch_crashes=False)


if __name__ == "__main__":
    main()
