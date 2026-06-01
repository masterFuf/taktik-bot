"""Debug action helpers for the Instagram desktop bridge."""

from __future__ import annotations

from bridges.instagram.runtime.ipc import send_error, send_log, send_message


def connect_debug_device(device_id: str):
    """Connect a device for debug commands."""
    from taktik.core.shared.device.manager import DeviceManager

    send_log("debug", f"Connecting to device {device_id}...")
    device_manager = DeviceManager(device_id=device_id)
    if not device_manager.connect(verify_atx=False):
        send_error(f"Failed to connect to device {device_id}")
        return None

    send_log("info", f"Connected to device {device_id}")
    return device_manager.device


def analyze_current_screen(device) -> int:
    """Analyze current screen by capturing screenshot and UI dump."""
    try:
        import os
        import tempfile

        from taktik.utils.ui_dump import capture_screenshot, dump_ui_hierarchy

        output_dir = os.path.join(tempfile.gettempdir(), "taktik_debug")
        os.makedirs(output_dir, exist_ok=True)
        send_log("debug", f"Output directory: {output_dir}")

        send_log("debug", "Capturing screenshot...")
        screenshot_path = capture_screenshot(device, output_dir)

        send_log("debug", "Dumping UI hierarchy...")
        dump_path = dump_ui_hierarchy(device, output_dir)

        result = {
            "success": True,
            "screenshotPath": screenshot_path,
            "dumpPath": dump_path,
        }

        if screenshot_path:
            send_log("info", f"Screenshot saved: {screenshot_path}")
        else:
            send_log("warning", "Screenshot capture failed")

        if dump_path:
            send_log("info", f"UI dump: {dump_path}")
        else:
            send_log("warning", "UI dump failed")

        send_message("debug_result", **result)
        return 0

    except Exception as exc:  # noqa: BLE001
        import traceback

        send_error(f"Analyze error: {exc}")
        send_log("error", f"Traceback: {traceback.format_exc()}")
        return 1


def detect_problematic_pages(device) -> int:
    """Detect and handle problematic pages for the foreground app."""
    try:
        current_app = device.app_current()
        package = current_app.get("package", "")
        send_log("info", f"Current app: {package}")
    except Exception as exc:  # noqa: BLE001
        send_log("warning", f"Could not detect current app: {exc}")
        package = ""

    if "musically" in package or "tiktok" in package.lower():
        send_log("info", "TikTok detected - popup handling is managed by workflow popup_handler")
        detected = False
        handled = False
    else:
        send_log("info", "Using Instagram problematic page detector")
        from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector

        detector = ProblematicPageDetector(device, debug_mode=True)
        result_data = detector.detect_and_handle_problematic_pages()
        if isinstance(result_data, dict):
            detected = result_data.get("detected", False)
            handled = result_data.get("closed", False)
        else:
            detected = bool(result_data)
            handled = detected

    result = {
        "success": True,
        "detected": detected,
        "handled": handled,
    }

    if detected:
        send_log("info", "Problematic page detected and handled")
    else:
        send_log("info", "No problematic pages detected")

    send_message("debug_result", **result)
    return 0


__all__ = ["analyze_current_screen", "connect_debug_device", "detect_problematic_pages"]
