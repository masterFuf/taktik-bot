"""Media capture helpers for the Instagram Persona Analysis bridge."""

from __future__ import annotations

import base64
import io

from bridges.instagram.runtime.ipc import _ipc, logger


class PersonaMediaMixin:
    """Capture profile media artifacts for Persona Analysis."""

    def capture_profile_screenshot(self, nav, collected: dict) -> None:
        """Capture the current profile screen as a base64 JPEG data URI."""
        try:
            pil_img = nav.device.screenshot_pil()
            if pil_img:
                buf = io.BytesIO()
                pil_img.convert("RGB").save(buf, format="JPEG", quality=75)
                collected["profile_screenshot"] = (
                    "data:image/jpeg;base64,"
                    + base64.b64encode(buf.getvalue()).decode()
                )
                _ipc.status("screenshot_taken", "Screenshot du profil capturé")
                logger.info("[PersonaAnalysis] Profile screenshot captured")
        except Exception as exc:
            logger.warning(f"[PersonaAnalysis] Screenshot failed: {exc}")
