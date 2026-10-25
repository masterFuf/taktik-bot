"""The CLI registers the platforms' selectors when its entry module loads, before any command."""

import os
import subprocess
import sys

from taktik.cli.hosts import selector_platforms
from taktik.core.compat.selectors import platforms
from taktik.core.social_media.instagram.ui.selectors import domains as instagram_domains
from taktik.core.social_media.tiktok.ui.selectors import domains as tiktok_domains
from unit.paths import CORE


def test_the_cli_registers_each_platform_s_declaration(monkeypatch):
    monkeypatch.setattr(platforms, "_LOADERS", {})
    monkeypatch.setattr(platforms, "_LOADED", {})

    selector_platforms.register_selector_platforms()

    assert platforms.registered_platforms() == ("instagram", "tiktok")
    assert platforms.platform_selectors("instagram") is instagram_domains.CATALOGUES
    assert platforms.platform_selectors("tiktok") is tiktok_domains.CATALOGUES


def test_loading_the_entry_of_taktik_and_taktik_tiktok_registers_them(tmp_path):
    # A fresh process: the harness has registered both platforms in this one already.
    env = {**os.environ, "APPDATA": str(tmp_path), "TAKTIK_DATA_DIR": str(tmp_path),
           "TAKTIK_DB_PATH": str(tmp_path / "throwaway.db")}
    code = ("import taktik.cli.main\n"
            "from taktik.core.compat.selectors import platforms\n"
            "print(','.join(platforms.registered_platforms()), sorted(platforms._LOADED))\n")
    result = subprocess.run([sys.executable, "-c", code], cwd=str(CORE), env=env,
                            capture_output=True, text=True, timeout=120)

    assert result.returncode == 0, result.stderr[-2000:]
    # Registered, and nothing imported for it: a loader runs at the first read.
    assert result.stdout.strip().splitlines()[-1] == "instagram,tiktok []"
