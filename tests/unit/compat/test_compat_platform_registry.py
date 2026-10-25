"""compat names no platform: the host registers them at its start, and a read that finds nothing
says so, by name, instead of patching nothing in silence (`compat/selectors/platforms.py`)."""

import pytest
from loguru import logger

from taktik.core.compat.selectors import platforms, setup
from taktik.core.compat.selectors.platforms import (
    EmptySelectorTable,
    PlatformNotRegistered,
    PlatformSelectors,
    register_platform,
)
from taktik.core.shared.device import manager as manager_module


@pytest.fixture
def no_host(monkeypatch):
    """A process whose host registered no platform (the harness registers both, `conftest.py`)."""
    monkeypatch.setattr(platforms, "_LOADERS", {})
    monkeypatch.setattr(platforms, "_LOADED", {})


@pytest.fixture
def messages():
    seen = []
    handler = logger.add(lambda message: seen.append(str(message)), format="{message}")
    yield seen
    logger.remove(handler)


def _one_catalogue():
    return PlatformSelectors(domains={"sample": object()})


def test_an_override_for_a_platform_nobody_registered_is_a_named_error(no_host):
    # Before the registry, this call logged "Unknown app" and patched nothing (returned 0).
    with pytest.raises(PlatformNotRegistered, match=r"'youtube' \(registered: none\)"):
        setup.apply_version_overrides("youtube", "1.0.0")


def test_the_connection_patcher_of_a_host_that_registered_nothing_says_it(no_host):
    with pytest.raises(PlatformNotRegistered, match=r"registered: none"):
        setup.apply_overrides_for_device("serial-1")


def test_a_connection_without_registered_platforms_fails_with_those_words(no_host, messages, monkeypatch):
    monkeypatch.setattr(manager_module.u2, "connect", lambda device_id: object())
    manager = manager_module.DeviceManager()

    assert manager.connect("serial-1", verify_atx=False) is False
    assert any("No selector catalogue registered" in line and "serial-1" in line for line in messages)

    # Nothing was patched, so the next connection asks again instead of taking the phone as done.
    register_platform("tiktok", _one_catalogue)
    monkeypatch.setattr(
        "taktik.core.shared.device.app_inspection.get_installed_app_version", lambda *args: None
    )
    assert manager.connect("serial-1", verify_atx=False) is True


def test_a_platform_the_host_did_not_register_is_named_with_those_it_did(no_host):
    register_platform("tiktok", _one_catalogue)
    with pytest.raises(PlatformNotRegistered, match=r"'instagram' \(registered: tiktok\)"):
        platforms.platform_selectors("instagram")


def test_an_empty_table_is_refused_at_its_first_read(no_host):
    register_platform("instagram", lambda: PlatformSelectors(domains={}))
    with pytest.raises(EmptySelectorTable, match="'instagram' is empty"):
        setup.apply_version_overrides("instagram", "447.0.0.55.81")


def test_a_domain_without_its_catalogue_is_refused(no_host):
    register_platform("instagram", lambda: PlatformSelectors(domains={"post": None}))
    with pytest.raises(EmptySelectorTable, match="domains without a catalogue: post"):
        platforms.platform_selectors("instagram")


def test_registering_loads_nothing_until_the_first_read(no_host):
    loads = []
    register_platform("instagram", lambda: loads.append("instagram") or _one_catalogue())
    assert loads == []

    platforms.platform_selectors("instagram")
    platforms.platform_selectors("instagram")
    assert loads == ["instagram"]


def test_a_second_host_of_the_process_keeps_the_first_loader(no_host):
    first, second = _one_catalogue(), _one_catalogue()
    register_platform("instagram", lambda: first)
    register_platform("instagram", lambda: second)
    assert platforms.platform_selectors("instagram") is first
    assert platforms.registered_platforms() == ("instagram",)
