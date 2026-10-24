"""The control of an app by ADB alone, without a uiautomator2 connection: the forced stop, and the
language Android gives one app (its per-app language)."""

from typing import List, Optional

from loguru import logger

from taktik.core.shared.device.apps import get_app_config, packages_for_platform
from taktik.core.shared.device.adb import run_adb_shell_process


def force_stop_app(device_id: str, platform: str) -> bool:
    """
    Force-stop a platform app on the given device using ADB.

    Does not require an active uiautomator2 connection, so it is safe to call
    from cleanup/finally paths after a workflow ends.
    """
    config = get_app_config(platform)
    if not config:
        logger.warning(f"[AppService] Unknown platform '{platform}' for force-stop")
        return False

    success = False
    for package_name in packages_for_platform(platform):
        try:
            result = run_adb_shell_process(
                device_id,
                ["am", "force-stop", package_name],
                text=False,
                timeout=5,
            )
            if result.returncode == 0:
                logger.info(f"[AppService] Closed {platform} ({package_name}) on {device_id}")
                success = True
                break
        except Exception as exc:
            logger.warning(f"[AppService] Could not force-stop {platform} ({package_name}): {exc}")

    if not success:
        logger.warning(f"[AppService] force_stop_app failed for {platform} on {device_id}")
    return success


# The per-app language (Android 13 and later): Settings > Apps > <app> > Language, set by
# `cmd locale`. An app's own language picker can keep a choice Android never applies (Instagram 410
# on Android 17); this one, the app receives from Android at its next start.

def set_app_locale(device_id: str, package: str, language_tag: str) -> bool:
    """Give `package` the per-app language `language_tag` ("en", "en-GB", "fr-CA"), then ask Android
    for it back: True only when Android holds it. Takes effect at the app's next start.

    Before Android 13 the phone has no `cmd locale`: a refusal, like any failure, is logged with what
    the phone answered and returns False.
    """
    command = ["cmd", "locale", "set-app-locales", package, "--locales", language_tag]
    try:
        answer = run_adb_shell_process(device_id, command, timeout=10)
    except Exception as exc:
        logger.warning(f"[AppLocale] {package}: could not run set-app-locales: {exc}")
        return False
    if answer.returncode != 0:
        said = (answer.stdout or answer.stderr or "").strip()
        logger.warning(f"[AppLocale] {package}: the phone refused set-app-locales "
                       f"(code {answer.returncode}): {said or 'no answer'}")
        return False

    held = read_app_locales(device_id, package)
    if held is None:
        return False
    if _same_tag(language_tag, held):
        logger.info(f"[AppLocale] {package}: Android holds the per-app language {language_tag}")
        return True
    logger.warning(f"[AppLocale] {package}: asked for {language_tag}, Android holds {held}")
    return False


def read_app_locales(device_id: str, package: str) -> Optional[List[str]]:
    """The per-app languages Android holds for `package`, in order; [] when it follows the phone's
    language. None when the phone did not say (no `cmd locale`, adb failed, an answer not read): logged.
    """
    command = ["cmd", "locale", "get-app-locales", package]
    try:
        answer = run_adb_shell_process(device_id, command, timeout=10)
    except Exception as exc:
        logger.warning(f"[AppLocale] {package}: could not run get-app-locales: {exc}")
        return None
    out = (answer.stdout or "").strip()
    # "Locales for <package> for user 0 are [en-US,fr-FR]"
    start, end = out.rfind("["), out.rfind("]")
    if answer.returncode != 0 or start < 0 or end < start:
        logger.warning(f"[AppLocale] {package}: get-app-locales answered (code {answer.returncode}): "
                       f"{out or (answer.stderr or '').strip() or 'nothing'}")
        return None
    return [tag.strip() for tag in out[start + 1:end].split(",") if tag.strip()]


def _same_tag(language_tag: str, held: List[str]) -> bool:
    """Is `language_tag` the first per-app language Android holds? Android may write `en_US` or `en-us`."""
    if not held:
        return False
    return held[0].replace("_", "-").lower() == language_tag.replace("_", "-").lower()
