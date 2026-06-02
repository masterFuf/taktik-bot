"""Lifecycle helpers for the compat workflow diagnostic bridge."""

import sys

from loguru import logger

from bridges.compat.diagnostics.runtime.workflow_test.observability import clear_active_watchdog, set_active_tracer


def init_automation(app_name: str, conn, ipc):
    def _on_xpath(call):
        ipc.send(
            "selector_event",
            xpath=call.xpath,
            found=call.found,
            elapsed_ms=call.elapsed_ms,
            step=call.step,
            error=call.error,
            screen=call.screen,
        )

    from taktik.core.compat.selectors.tracer import SelectorTracer

    tracer = SelectorTracer(on_xpath_call=_on_xpath)

    try:
        from taktik.core.database import configure_db_service

        configure_db_service()

        automation = None
        if app_name == "instagram":
            from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation

            automation = InstagramAutomation(conn.device_manager)
            device = automation.device
        else:
            device = conn.device_manager

        tracer.attach(device)
        set_active_tracer(tracer)

        ipc.send("step", step="init_automation", status="done", message="Automation ready, tracer attached")
        return tracer, automation, device
    except Exception as exc:
        ipc.send("error", error=f"Automation init failed: {exc}", error_code="AUTOMATION_INIT_ERROR")
        logger.exception("Automation init failed")
        sys.exit(1)


def apply_version_overrides(app_name: str, version: str, ipc) -> None:
    ipc.send(
        "step",
        step="version_overrides",
        status="running",
        message=f"Applying selector overrides for {app_name} v{version}...",
    )
    try:
        from taktik.core.compat.selectors.setup import apply_version_overrides as apply_overrides

        patched_count = apply_overrides(app_name, version)
        ipc.send("step", step="version_overrides", status="done", message=f"Patched {patched_count} selector(s) for v{version}")
        if patched_count > 0:
            ipc.send(
                "action_event",
                action="version_overrides_applied",
                username="",
                success=True,
                data={"version": version, "patched": patched_count},
            )
    except Exception as exc:
        logger.warning(f"Version override failed (non-fatal): {exc}")
        ipc.send("step", step="version_overrides", status="done", message="Version overrides: skipped (error)")


def detect_instagram_language(app_name: str, device, ipc) -> None:
    if app_name != "instagram":
        return

    ipc.send("step", step="language_detect", status="running", message="Detecting app language...")
    try:
        from taktik.core.social_media.instagram.ui.language import detect_and_optimize

        detected_lang = detect_and_optimize(device)
        ipc.send("step", step="language_detect", status="done", message=f"Language: {detected_lang.upper()}")
        ipc.send("action_event", action="language_detected", username="", success=True, data={"language": detected_lang})
    except Exception as exc:
        logger.warning(f"Language detection failed (non-fatal): {exc}")
        ipc.send("step", step="language_detect", status="done", message="Language: unknown (detection failed)")


def stop_watchdog(watchdog, ipc) -> None:
    if not watchdog:
        return

    try:
        watchdog.stop()
        clear_active_watchdog()
        ipc.send("action_event", action="watchdog_stopped", username="", success=True, data=watchdog.stats)
    except Exception:
        clear_active_watchdog()


__all__ = [
    "apply_version_overrides",
    "detect_instagram_language",
    "init_automation",
    "stop_watchdog",
]
