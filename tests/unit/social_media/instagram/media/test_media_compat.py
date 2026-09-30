from pathlib import Path

from taktik.core.social_media.instagram.media import MediaCaptureService as OwnerMediaCaptureService
from taktik.core.social_media.instagram.media import ProxyManager as OwnerProxyManager
from taktik.core.social_media.instagram.media import MediaCaptureService, ProxyManager
from taktik.core.social_media.instagram.media.proxy import proxy_manager
from taktik.core.social_media.instagram.media.proxy.proxy_manager import resolve_media_scripts_dir


def test_instagram_media_package_exports_owner_symbols():
    assert MediaCaptureService is OwnerMediaCaptureService
    assert ProxyManager is OwnerProxyManager


def test_the_media_proxy_finds_its_addon_and_frida_script_next_to_it():
    folder = resolve_media_scripts_dir(Path(proxy_manager.__file__))

    assert folder == Path(proxy_manager.__file__).resolve().parent
    assert (folder / "mitm_addon.py").is_file()
    assert (folder / "frida_ssl_bypass.js").is_file()
