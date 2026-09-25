"""Two processes on one phone (a run and the Lab) share the pushed-media registry: neither may
lose the other's entries. A lost entry only leaves a file on the phone, never deletes one."""

import os
import time

import pytest

from taktik.core.shared.device import pushed_media_registry as registry


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TAKTIK_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(registry, "LOCK_WAIT_SECONDS", 0.2)


def _lock_path(device):
    return registry._registry_file(device) + ".lock"


def test_a_record_waits_for_the_lock_and_gives_up_without_writing():
    registry.record("dev", "/sdcard/DCIM/Camera/IMG_1.jpg", 10)
    open(_lock_path("dev"), "w").close()
    assert not registry.record("dev", "/sdcard/DCIM/Camera/IMG_2.jpg", 20)
    os.remove(_lock_path("dev"))
    assert [e["path"] for e in registry.load("dev")] == ["/sdcard/DCIM/Camera/IMG_1.jpg"]


def test_a_lock_left_by_a_dead_process_is_taken_over(monkeypatch):
    open(_lock_path("dev"), "w").close()
    old = time.time() - registry.STALE_LOCK_SECONDS - 5
    os.utime(_lock_path("dev"), (old, old))
    assert registry.record("dev", "/sdcard/DCIM/Camera/IMG_1.jpg", 10)
    assert not os.path.exists(_lock_path("dev"))


def test_forgetting_keeps_what_another_process_recorded_meanwhile():
    registry.record("dev", "/sdcard/DCIM/Camera/IMG_1.jpg", 10)
    snapshot = registry.load("dev")              # the purge read the list...
    registry.record("dev", "/sdcard/DCIM/Camera/IMG_2.jpg", 20)  # ...another push landed...
    registry.forget("dev", [e["path"] for e in snapshot])        # ...the purge drops what it deleted
    assert [e["path"] for e in registry.load("dev")] == ["/sdcard/DCIM/Camera/IMG_2.jpg"]
