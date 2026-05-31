# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('C:\\Users\\kevin\\Documents\\taktik-desktop\\bot\\taktik', 'taktik'), ('C:\\Users\\kevin\\Documents\\taktik-desktop\\bot\\bridges', 'bridges'), ('C:\\Users\\kevin\\AppData\\Local\\Programs\\Python\\Python310\\lib\\site-packages\\uiautomator2\\assets', 'uiautomator2/assets')]
binaries = []
hiddenimports = ['taktik', 'taktik.core', 'taktik.core.database', 'taktik.core.license', 'taktik.core.database.api_client', 'taktik.core.license.unified_license_manager', 'taktik.core.social_media.tiktok', 'bridges.common', 'bridges.instagram.automation.desktop', 'bridges.instagram.engagement.dm', 'bridges.instagram.scraping.scraping', 'bridges.instagram.engagement.cold_dm', 'bridges.instagram.engagement.smart_comment', 'bridges.instagram.account.account', 'bridges.instagram.agent.taktik_agent', 'bridges.instagram.analysis.persona', 'bridges.tiktok.workflows.dispatcher', 'bridges.tiktok.automation.unfollow', 'bridges.tiktok.engagement.dm_outreach', 'bridges.tiktok.scraping.scraping', 'bridges.tiktok.account.account', 'bridges.tiktok.publish.publish', 'bridges.threads.workflows.dispatcher', 'bridges.gmail.account.account', 'bridges.youtube.account.account', 'bridges.youtube.publish.upload', 'bridges.youtube.diagnostics.action_test', 'bridges.compat.diagnostics.compat', 'bridges.compat.diagnostics.selector_test', 'bridges.compat.diagnostics.workflow_test', 'bridges.compat.diagnostics.action_test', 'bridges.compat.diagnostics.tiktok_action_test', 'adbutils', 'uiautomator2', 'loguru', 'requests', 'httpx', 'yaml', 'rich', 'typer', 'pydantic']
hiddenimports += collect_submodules('bridges.tiktok')
tmp_ret = collect_all('taktik')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('bridges')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('rich')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['bridges\\launcher.py'],
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
