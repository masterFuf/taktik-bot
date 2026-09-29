"""The app primitives of a phone: the package catalog of each platform, the package a run really
drives (a clone, an installed variant), the forced stop without a connection, and the app lifecycle
of a connected phone (`AppService`).

What each one answers is pinned here, on doubles of the phone (no device, no adb): the bridges, the
CLI and the Lab start every run through them.
"""

from types import SimpleNamespace

import pytest

from taktik.core.shared.device import app_control, app_manager, app_resolution, apps

INSTAGRAM = "com.instagram.android"
INSTAGRAM_ACTIVITY = "com.instagram.mainactivity.InstagramMainActivity"
TIKTOK = "com.zhiliaoapp.musically"
TRILL = "com.ss.android.ugc.trill"
AWEME = "com.ss.android.ugc.aweme"


# -------------------------------------------------------------------------------------- the catalog

def test_the_catalog_hands_out_a_copy():
    config = apps.get_app_config("instagram")
    config["package"] = "com.changed"

    assert apps.get_app_config("instagram")["package"] == INSTAGRAM


def test_the_catalog_of_each_platform():
    assert apps.known_platforms() == ["instagram", "tiktok", "threads", "gmail", "youtube"]
    assert apps.get_app_config("instagram") == {
        "package": INSTAGRAM, "activity": INSTAGRAM_ACTIVITY, "launch_wait": 4, "stop_wait": 1}
    assert apps.get_app_config("tiktok")["stop_wait"] == 1.5
    assert apps.get_app_config("gmail")["launch_wait"] == 3


def test_an_unknown_platform_has_no_config_no_package_no_variant():
    assert apps.get_app_config("myspace") is None
    assert apps.packages_for_platform("myspace") == []
    assert apps.alternatives_for_platform("myspace") == []


def test_the_packages_of_a_platform_are_its_default_then_its_variants_once():
    assert apps.packages_for_platform("tiktok") == [TIKTOK, TRILL, AWEME]
    assert apps.packages_for_platform("instagram") == [INSTAGRAM]


def test_the_variants_are_a_copy():
    variants = apps.alternatives_for_platform("tiktok")
    variants.append("com.changed")

    assert apps.alternatives_for_platform("tiktok") == [TIKTOK, TRILL, AWEME]


# ------------------------------------------------------------------------ the package a run drives

class _Phone:
    """A device manager that answers which packages are installed, and records each question."""

    def __init__(self, installed=()):
        self.installed = set(installed)
        self.asked = []

    def is_app_installed(self, package):
        self.asked.append(package)
        return package in self.installed


class _Untouchable:
    """A connection the resolution must not ask anything."""

    @property
    def device_manager(self):
        raise AssertionError("the phone was asked")


def _connection(manager):
    return SimpleNamespace(device_manager=manager)


def test_an_unknown_platform_is_refused_with_the_known_ones():
    with pytest.raises(ValueError, match=r"Unknown platform 'myspace'.*instagram"):
        app_resolution.resolve_app_config(_Untouchable(), "myspace")


def test_a_clone_package_replaces_the_default_without_asking_the_phone():
    config = app_resolution.resolve_app_config(_Untouchable(), "instagram", "com.other.clone")

    assert config["package"] == "com.other.clone"
    assert config["activity"] == INSTAGRAM_ACTIVITY


def test_a_taktik_clone_is_launched_without_an_explicit_activity():
    config = app_resolution.resolve_app_config(_Untouchable(), "instagram", "com.taktik.ig1")

    assert config["package"] == "com.taktik.ig1"
    assert config["activity"] is None


def test_the_default_package_named_as_override_keeps_the_default():
    config = app_resolution.resolve_app_config(_Untouchable(), "instagram", INSTAGRAM)

    assert config == apps.get_app_config("instagram")


def test_without_a_device_manager_the_default_stays():
    assert app_resolution.resolve_app_config(_connection(None), "tiktok") == apps.get_app_config("tiktok")


def test_a_platform_without_variants_does_not_ask_the_phone():
    phone = _Phone()

    assert app_resolution.resolve_app_config(_connection(phone), "instagram")["package"] == INSTAGRAM
    assert phone.asked == []


def test_the_first_installed_variant_is_the_one_driven():
    phone = _Phone(installed={TRILL, AWEME})

    assert app_resolution.resolve_app_config(_connection(phone), "tiktok")["package"] == TRILL
    assert phone.asked == [TIKTOK, TRILL]


def test_the_default_installed_is_kept():
    phone = _Phone(installed={TIKTOK, TRILL})

    assert app_resolution.resolve_app_config(_connection(phone), "tiktok")["package"] == TIKTOK
    assert phone.asked == [TIKTOK]


def test_no_variant_installed_keeps_the_default_after_asking_each():
    phone = _Phone()

    assert app_resolution.resolve_app_config(_connection(phone), "tiktok")["package"] == TIKTOK
    assert phone.asked == [TIKTOK, TRILL, AWEME]


# ---------------------------------------------------------------------------------- the forced stop

class _Adb:
    """`run_adb_shell_process`: one answer per call (a return code, or an exception to raise)."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, device_id, args, **kwargs):
        self.calls.append((device_id, args, kwargs))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return SimpleNamespace(returncode=answer)


def test_an_unknown_platform_is_not_stopped(monkeypatch):
    adb = _Adb()
    monkeypatch.setattr(app_control, "run_adb_shell_process", adb)

    assert app_control.force_stop_app("SERIAL", "myspace") is False
    assert adb.calls == []


def test_the_first_package_stopped_ends_the_forced_stop(monkeypatch):
    adb = _Adb(0)
    monkeypatch.setattr(app_control, "run_adb_shell_process", adb)

    assert app_control.force_stop_app("SERIAL", "tiktok") is True
    assert adb.calls == [("SERIAL", ["am", "force-stop", TIKTOK], {"text": False, "timeout": 5})]


def test_a_refused_or_failed_stop_tries_the_next_package(monkeypatch):
    adb = _Adb(1, OSError("adb gone"), 0)
    monkeypatch.setattr(app_control, "run_adb_shell_process", adb)

    assert app_control.force_stop_app("SERIAL", "tiktok") is True
    assert [call[1][2] for call in adb.calls] == [TIKTOK, TRILL, AWEME]


def test_no_package_stopped_is_a_failure(monkeypatch):
    adb = _Adb(1, 1, 1)
    monkeypatch.setattr(app_control, "run_adb_shell_process", adb)

    assert app_control.force_stop_app("SERIAL", "tiktok") is False
    assert len(adb.calls) == 3


def test_the_app_manager_module_still_names_the_forced_stop():
    """Callers and test rigs reach it there; it is the one of `app_control`."""
    assert app_manager.force_stop_app is app_control.force_stop_app


# ------------------------------------------------------------------ the app lifecycle (AppService)

class _Manager:
    """The device manager of a connected phone, recorded."""

    def __init__(self, installed=True, launched=True, stopped=True):
        self.installed, self.launched, self.stopped = installed, launched, stopped
        self.calls = []

    def is_app_installed(self, package):
        self.calls.append(("installed", package))
        return self.installed

    def launch_app(self, package, activity=None):
        self.calls.append(("launch", package, activity))
        return self.launched

    def stop_app(self, package):
        self.calls.append(("stop", package))
        return self.stopped


@pytest.fixture
def slept(monkeypatch):
    pauses = []
    monkeypatch.setattr(app_manager.time, "sleep", pauses.append)
    return pauses


def _service(manager, platform="instagram", package=None, device="DEVICE"):
    connection = SimpleNamespace(device_manager=manager, device=device, device_id="SERIAL")
    return app_manager.AppService(connection, platform=platform, package_override=package)


def test_the_service_drives_the_resolved_package():
    service = _service(_Manager(), package="com.taktik.ig1")

    assert service.package == "com.taktik.ig1"
    assert service.activity is None


def test_installed_asks_the_manager_for_the_package():
    manager = _Manager(installed=False)

    assert _service(manager).is_installed() is False
    assert manager.calls == [("installed", INSTAGRAM)]


def test_a_launch_waits_the_launch_delay_of_the_platform(slept):
    manager = _Manager()

    assert _service(manager).launch() is True
    assert manager.calls == [("launch", INSTAGRAM, INSTAGRAM_ACTIVITY)]
    assert slept == [4]


def test_a_failed_launch_does_not_wait(slept):
    assert _service(_Manager(launched=False)).launch() is False
    assert slept == []


def test_a_stop_waits_the_stop_delay_even_when_it_failed(slept):
    manager = _Manager(stopped=False)

    assert _service(manager, platform="tiktok").stop() is False
    assert manager.calls == [("installed", TIKTOK), ("stop", TIKTOK)]
    assert slept == [1.5]


def test_a_restart_is_a_stop_then_a_launch(slept):
    manager = _Manager(launched=False)

    assert _service(manager).restart() is False
    assert manager.calls == [("stop", INSTAGRAM), ("launch", INSTAGRAM, INSTAGRAM_ACTIVITY)]
    assert slept == [1]


def test_without_a_manager_nothing_runs(slept):
    service = _service(None)

    assert (service.is_installed(), service.launch(), service.stop()) == (False, False, False)
    assert slept == []


def test_running_asks_the_foreground_of_the_connected_device(monkeypatch):
    asked = []
    monkeypatch.setattr(app_manager, "is_app_running",
                        lambda device, package, platform: asked.append((device, package, platform)) or True)

    assert _service(_Manager(), package="com.other.clone").is_running() is True
    assert asked == [("DEVICE", "com.other.clone", "instagram")]


def test_the_installed_version_is_read_on_the_serial(monkeypatch):
    asked = []
    monkeypatch.setattr(app_manager, "get_installed_app_version",
                        lambda device_id, package, platform: asked.append((device_id, package, platform)) or "410.0")

    assert _service(_Manager()).get_installed_version() == "410.0"
    assert asked == [("SERIAL", INSTAGRAM, "instagram")]
