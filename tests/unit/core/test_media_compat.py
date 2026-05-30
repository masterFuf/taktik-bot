from pathlib import Path

from taktik.core.media import MediaCaptureService, ProxyManager
from taktik.core.media.capture.media_capture import MediaCaptureService as LegacyMediaCaptureService
from taktik.core.media.proxy.proxy_manager import ProxyManager as LegacyProxyManager
from taktik.core.social_media.instagram.media import MediaCaptureService as OwnerMediaCaptureService
from taktik.core.social_media.instagram.media import ProxyManager as OwnerProxyManager
from taktik.core.social_media.instagram.media.proxy.proxy_manager import resolve_media_scripts_dir


def test_core_media_reexports_instagram_owner_symbols():
    assert MediaCaptureService is OwnerMediaCaptureService
    assert ProxyManager is OwnerProxyManager
    assert LegacyMediaCaptureService is OwnerMediaCaptureService
    assert LegacyProxyManager is OwnerProxyManager


def test_media_scripts_dir_resolution_points_to_repo_scripts():
    scripts_dir = resolve_media_scripts_dir(Path(__file__))

    assert scripts_dir.name == "scripts"
    assert (scripts_dir / "mitm_addon.py").exists()
    assert (scripts_dir / "frida_ssl_bypass.js").exists()
