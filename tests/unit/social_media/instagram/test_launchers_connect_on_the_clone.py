"""Each Instagram launcher reads the clone it runs on, and hands it to the host's connection.

The DM inbox, the notifications, the Taktik Agent, the cold DM and the story relay took a device
their host had already connected: the bridge read `packageName` itself, and a CLI run got the
clone only when its handler thought of reading it (the story relay never did). The launcher now
reads the package with the rest of the payload (`package_name_from_payload`, the account flows'
reading) and asks the injected `connect` for the phone on that package, after its refusals.

The automation read `packageName` on its own (no `package_name`, no trimming), its CLI handler adding
the alias for it; it reads through the same helper since decision D3 of 2026-09-27.
"""

from __future__ import annotations

import pytest

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

    return run_instagram_automation({"workflowType": "feed", **payload}, device_manager=object(),
                                    instagram_start=connect)


LAUNCHERS = {
    "automation": (_automation, {}),
    "dm_read": (_dm, {"command": "read"}),
    "dm_send": (_dm, {"command": "send", "username": "ana", "message": "hi"}),
    "notifications": (_notifications, {"command": "scan"}),
    "taktik_agent": (_agent, {}),
    "cold_dm": (_cold_dm, {}),
    "story_relay": (_story_relay, {}),
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
