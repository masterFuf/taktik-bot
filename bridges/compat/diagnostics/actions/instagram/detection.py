"""Detection actions for Instagram compat diagnostics."""

import os
import tempfile
import time

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


@action("detection.is_home_screen")
def is_home_screen(a, p):
    result = a.detection.is_on_home_screen()
    logger.info(f"Home screen: {result}")
    return result


@action("detection.is_profile_screen")
def is_profile_screen(a, p):
    result = a.detection.is_on_profile_screen()
    logger.info(f"Profile screen: {result}")
    return result


@action("detection.is_post_open")
def is_post_open(a, p):
    result = a.detection.is_on_post_screen()
    logger.info(f"Post open: {result}")
    return result


@action("detection.get_current_screen")
def get_current_screen(a, p):
    try:
        app = a.device._device.app_current()
        logger.info(f"Current app: {app.get('package')} / activity: {app.get('activity')}")
    except Exception as exc:
        logger.error(f"Could not get current app: {exc}")
    return True


@action("detection.dump_xml")
def dump_xml(a, p):
    try:
        xml = a.device.get_xml_dump()
        if xml:
            preview = xml[:2000] + ("..." if len(xml) > 2000 else "")
            logger.info(f"XML dump preview ({len(xml)} chars):\n{preview}")
        else:
            logger.warning("XML dump returned empty")
    except Exception as exc:
        logger.error(f"XML dump failed: {exc}")
    return True


@action("detection.screenshot")
def take_screenshot(a, p):
    path = os.path.join(tempfile.gettempdir(), "taktik_debug", f"action_test_{int(time.time())}.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    result = a.device.screenshot(path)
    if result:
        logger.info(f"Screenshot saved: {path}")
    else:
        logger.error("Screenshot failed")
    return result

