# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('C:\\Users\\kevin\\Documents\\taktik-desktop\\bot\\taktik', 'taktik'), ('C:\\Users\\kevin\\Documents\\taktik-desktop\\bot\\bridges', 'bridges'), ('C:\\Users\\kevin\\AppData\\Local\\Programs\\Python\\Python310\\lib\\site-packages\\uiautomator2\\assets', 'uiautomator2/assets')]
binaries = []
hiddenimports = ['taktik', 'taktik.core', 'taktik.core.database', 'taktik.core.license', 'taktik.core.database.api_client', 'taktik.core.license.unified_license_manager', 'taktik.core.social_media.tiktok', 'taktik.core.email', 'bridges.common', 'bridges.instagram.desktop_bridge', 'bridges.instagram.dm_bridge', 'bridges.instagram.scraping_bridge', 'bridges.instagram.cold_dm_bridge', 'bridges.instagram.discovery_bridge', 'bridges.instagram.smart_comment_bridge', 'bridges.instagram.account_bridge', 'bridges.instagram.taktik_agent_bridge', 'bridges.tiktok.tiktok_bridge', 'bridges.tiktok.tiktok_unfollow_bridge', 'bridges.tiktok.dm_outreach_bridge', 'bridges.tiktok.scraping_bridge', 'bridges.tiktok.tiktok_account_bridge', 'bridges.tiktok.tiktok_publish_bridge', 'bridges.threads.threads_bridge', 'bridges.gmail.gmail_account_bridge', 'bridges.youtube.youtube_account_bridge', 'bridges.youtube.youtube_upload_bridge', 'bridges.youtube.youtube_action_test_bridge', 'bridges.compat.compat_bridge', 'bridges.compat.selector_test_bridge', 'bridges.compat.workflow_test_bridge', 'bridges.compat.action_test_bridge', 'bridges.compat.tiktok_action_test_bridge', 'adbutils', 'uiautomator2', 'loguru', 'requests', 'httpx', 'yaml', 'rich', 'typer', 'pydantic']
hiddenimports += collect_submodules('bridges.tiktok')
tmp_ret = collect_all('taktik')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('bridges')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('rich')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['..\\bridges\\launcher.py'],
    pathex=['C:\\Users\\kevin\\Documents\\taktik-desktop\\bot'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['cv2', 'matplotlib', 'tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='taktik_launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
