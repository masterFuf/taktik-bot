"""Each Instagram launcher reads the clone it runs on, and hands it to the host's connection.

The DM inbox, the notifications, the Taktik Agent, the cold DM and the story relay took a device
their host had already connected: the bridge read `packageName` itself, and a CLI run got the
clone only when its handler thought of reading it (the story relay never did). The launcher now
reads the package with the rest of the payload (`package_name_from_payload`, the account flows'
reading) and asks the injected `connect` for the phone on that package, after its refusals.

The automation read `packageName` on its own (no `package_name`, no trimming), its CLI handler adding
the alias for it; it reads through the same helper since decision D3 of 2026-09-27, and asks its host
for the phone through `connect` too since 2026-10-18 (it was handed a phone its host had connected).
The scraping asked the same way but read `packageName` by hand (`payload.get("packageName") or None`:
no `package_name`, no trimming), a second reading of the same field; it reads through the same helper
since 2026-10-26, so one payload names one package for every launcher.

The hosts read it a second time: the automation bridge built its app on its own `packageName` and
ignored the package its `connect` was handed, the persona bridge read it by hand. The structural test
at the end names any reading of the field on the Instagram side outside `startup.py`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from unit.paths import CORE

CLONE = "com.instagram.clone"


class Connected(Exception):
    """The launcher asked for the phone: what it asked with is what the test reads."""


def _connect(seen):
    def connect(package_name, *rest):
        seen.append(package_name)
        raise Connected()

    return connect


def _dm(payload, connect):
    from taktik.core.social_media.instagram.workflows.dm.agent_handler import run_instagram_dm

    return run_instagram_dm(payload, connect=connect)


def _notifications(payload, connect):
    from taktik.core.social_media.instagram.workflows.notifications.agent_handler import (
        run_instagram_notifications,
    )

    return run_instagram_notifications(payload, connect=connect)


def _agent(payload, connect):
    from taktik.core.social_media.instagram.workflows.agent.agent_handler import run_instagram_agent

    return run_instagram_agent({"openrouter_api_key": "sk-test", **payload}, connect=connect)


def _cold_dm(payload, connect):
    from taktik.core.social_media.instagram.workflows.cold_dm.agent_handler import run_instagram_cold_dm

    return run_instagram_cold_dm({"recipients": ["ana"], "messages": ["hi"], **payload}, connect=connect)


def _story_relay(payload, connect):
    from taktik.core.social_media.instagram.workflows.tasks.agent_handler import run_instagram_story_relay

    return run_instagram_story_relay({"source_username": "source", **payload}, connect=connect)


def _automation(payload, connect):
    from taktik.core.social_media.instagram.workflows.automation.agent_handler import run_instagram_automation

    return run_instagram_automation({"workflowType": "feed", **payload}, connect=connect)


def _scraping(payload, connect):
    from taktik.core.social_media.instagram.workflows.scraping.agent_handler import run_instagram_scraping

    return run_instagram_scraping({"type": "usernames", "usernames": ["ana"], **payload}, connect=connect)


LAUNCHERS = {
    "automation": (_automation, {}),
    "dm_read": (_dm, {"command": "read"}),
    "dm_send": (_dm, {"command": "send", "username": "ana", "message": "hi"}),
    "notifications": (_notifications, {"command": "scan"}),
    "taktik_agent": (_agent, {}),
    "cold_dm": (_cold_dm, {}),
    "story_relay": (_story_relay, {}),
    "scraping": (_scraping, {}),
}


@pytest.mark.parametrize("name", LAUNCHERS)
def test_the_clone_of_the_payload_is_the_one_connected(name):
    launch, payload = LAUNCHERS[name]
    seen = []

    with pytest.raises(Connected):
        launch({**payload, "packageName": CLONE}, _connect(seen))

    assert seen == [CLONE]


@pytest.mark.parametrize("name", LAUNCHERS)
def test_the_clone_under_its_cli_name_is_the_one_connected(name):
    launch, payload = LAUNCHERS[name]
    seen = []

    with pytest.raises(Connected):
        launch({**payload, "package_name": f" {CLONE} "}, _connect(seen))

    assert seen == [CLONE]


@pytest.mark.parametrize("name", LAUNCHERS)
def test_without_a_clone_the_installed_instagram_is_connected(name):
    launch, payload = LAUNCHERS[name]
    seen = []

    with pytest.raises(Connected):
        launch(payload, _connect(seen))

    assert seen == [None]


REFUSED = {
    "automation": (_automation, {"limits": {"maxProfiles": 501}}),
    "scraping": (_scraping, {"usernames": []}),
    "dm_send": (_dm, {"command": "send", "username": "ana"}),
    "notifications": (_notifications, {"command": "reply"}),
    "cold_dm": (_cold_dm, {"recipients": []}),
    "story_relay": (_story_relay, {"source_username": ""}),
}


@pytest.mark.parametrize("name", REFUSED)
def test_a_refused_run_never_connects(name):
    launch, payload = REFUSED[name]
    seen = []

    with pytest.raises(ValueError):
        launch({**payload, "packageName": CLONE}, _connect(seen))

    assert seen == []


# One reading of the clone: `package_name_from_payload`. The Instagram side is every file under a folder
# named `instagram`, or whose name says Instagram, in the bot and its bridges; the contract declares the
# field (`instagram_package_field`), it does not read it.
HOME = CORE / "taktik" / "core" / "social_media" / "instagram" / "workflows" / "common" / "startup.py"
PACKAGE_KEYS = {"packageName", "package_name"}
NOT_A_READING = {"getattr", "hasattr", "setattr", "delattr"}


def _instagram_side() -> list[Path]:
    files = []
    for root in ("taktik", "bridges"):
        for path in sorted((CORE / root).rglob("*.py")):
            relative = path.relative_to(CORE)
            if relative.parts[:3] == ("taktik", "core", "contract"):
                continue
            if "instagram" in relative.parts[:-1] or "instagram" in path.stem:
                files.append(path)
    return files


def _is_package_key(node) -> bool:
    return isinstance(node, ast.Constant) and node.value in PACKAGE_KEYS


def _package_readings(tree: ast.AST) -> list[int]:
    """Lines that read the clone's field from a mapping: `.get`/`.pop`/`.setdefault`, `[...]`, `in`, or a
    helper handed the key (`value_param(payload, "packageName")`). Writing the key (a dict literal) is
    not a reading."""
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) and _is_package_key(node.slice):
            lines.append(node.lineno)
        elif isinstance(node, ast.Compare) and _is_package_key(node.left) and any(
                isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
            lines.append(node.lineno)
        elif isinstance(node, ast.Call) and any(_is_package_key(arg) for arg in node.args):
            name = node.func.id if isinstance(node.func, ast.Name) else None
            if name not in NOT_A_READING:
                lines.append(node.lineno)
    return sorted(set(lines))


def test_no_instagram_code_reads_the_clone_outside_its_reader():
    files = _instagram_side()
    assert HOME in files and len(files) > 300, "the Instagram side is no longer where this test looks"
    found = []
    for path in files:
        if path == HOME:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        found += [f"{path.relative_to(CORE).as_posix()}:{line}" for line in _package_readings(tree)]
    assert not found, (
        "read the clone with `package_name_from_payload` (taktik/core/social_media/instagram/workflows/"
        "common/startup.py), or take the package the launcher hands to `connect`: " + ", ".join(found)
    )


@pytest.mark.parametrize("source, lines", [
    ('package = config.get("packageName")\n', [1]),
    ('package = payload.pop("package_name", None)\n', [1]),
    ('package = payload["packageName"]\n', [1]),
    ('if "packageName" in payload:\n    pass\n', [1]),
    ('package = value_param(merged, "package_name")\n', [1]),
    ('report = {"packageName": package}\n', []),
    ('package = getattr(automation, "package_name", None)\n', []),
    ('payload["packageName"] = package\n', []),
], ids=["get", "pop", "subscript", "in", "helper", "written", "attribute", "assigned"])
def test_the_structural_check_sees_a_reading_by_hand(source, lines):
    assert _package_readings(ast.parse(source)) == lines
