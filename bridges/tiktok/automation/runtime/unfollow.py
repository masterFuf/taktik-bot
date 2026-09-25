"""TikTok unfollow bridge runtime.

The run is `run_tiktok_unfollow` (core), the launcher the Agent handler
`tiktok.standalone.tiktok_unfollow` (and so the CLI) calls too: start TikTok, read the acting
account on the phone, unfollow as that account. This bridge unwraps the app's stdin payload
(`{device_id, config}`), rotates the IP when the page asks for it, and injects what is specific to
the desktop: the startup that prints on stdout, its IPC for the live events, the stop signal.
"""

from __future__ import annotations

from typing import Any, Dict

from bridges.common.device.network import enforce_pre_session_ip_rotation
from bridges.tiktok.runtime.ipc import _ipc, logger, send_error, send_status, set_workflow
from bridges.tiktok.runtime.startup import tiktok_startup_provider


def run_unfollow_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok Unfollow workflow."""
    from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.payload import (
        unfollow_config_from_payload,
    )

    device_id = config.get("deviceId")
    bot_username = config.get("botUsername")
    max_unfollows = unfollow_config_from_payload(config).max_unfollows

    if not device_id:
        send_error("No device ID provided")
        return False

    logger.info(f"👋 Starting TikTok Unfollow workflow on device: {device_id}")
    if bot_username:
        logger.info(f"📊 Bot account: @{bot_username}")
    logger.info(f"🎯 Max unfollows: {max_unfollows}")
    send_status("starting", f"Initializing TikTok Unfollow workflow on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.agent_handler import (
            run_tiktok_unfollow,
        )

        run_tiktok_unfollow(
            config,
            notifier=_ipc,
            tiktok_startup=tiktok_startup_provider(device_id),
            workflow_hook=set_workflow,
        )
        return True

    except ImportError as e:
        error_msg = f"Import error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as e:
        error_msg = f"Unfollow workflow error: {e}"
        logger.error(error_msg)
        send_error(error_msg)
        return False


class TikTokUnfollowBridge:
    """One `tiktok_unfollow_bridge` process: the app's `{device_id, config}`, the IP rotation the
    page asks for, then the run."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def run(self) -> int:
        logger.info("🎵 TikTok Unfollow Bridge starting...")
        try:
            device_id = self.config.get("device_id")
            config = self.config.get("config", {})
            config["deviceId"] = device_id

            logger.info(f"📋 Config received: device={device_id}, maxUnfollows={config.get('maxUnfollows', 20)}")

            # The page offers "reset IP before the run".
            if not enforce_pre_session_ip_rotation(config, device_id, ipc=_ipc, label="Unfollow"):
                return 1

            if run_unfollow_workflow(config):
                logger.success("✅ TikTok Unfollow workflow completed successfully")
                return 0

            logger.error("❌ TikTok Unfollow workflow failed")
            return 1
        except Exception as e:
            send_error(f"Startup error: {e}")
            logger.exception(f"Unexpected error: {e}")
            return 1


__all__ = ["TikTokUnfollowBridge", "run_unfollow_workflow"]
