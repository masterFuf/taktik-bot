"""Compatibility shim for the Instagram media capture service."""

from taktik.core.social_media.instagram.media.capture.media_capture import (
    MediaCapture,
    MediaCaptureService,
    ProfileCapture,
)

__all__ = ["MediaCapture", "MediaCaptureService", "ProfileCapture"]
