import subprocess

from taktik.core.social_media.tiktok.services.runtime.package_resolver import resolve_tiktok_package


def test_resolve_tiktok_package_uses_shared_package_variants():
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        package_name = command[-1]
        stdout = f"package:{package_name}\n" if package_name == "com.bytedance.trill" else ""
        return subprocess.CompletedProcess(args=command, returncode=0, stdout=stdout, stderr="")

    assert resolve_tiktok_package("device-1", run=fake_run) == "com.bytedance.trill"
    assert calls[-1][0] == [
        "adb",
        "-s",
        "device-1",
        "shell",
        "pm",
        "list",
        "packages",
        "com.bytedance.trill",
    ]
    assert calls[-1][1]["timeout"] == 10


def test_resolve_tiktok_package_falls_back_to_default():
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="",
            stderr="",
        )

    assert resolve_tiktok_package(
        "device-1",
        default="fallback.package",
        run=fake_run,
    ) == "fallback.package"
