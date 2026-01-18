"""
Build script to create standalone Python executables for TAKTIK Bot
Run with: python build_exe.py
"""

import PyInstaller.__main__
import os
import shutil

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Bot root directory (parent of scripts/)
BASE_DIR = os.path.dirname(SCRIPT_DIR)
DIST_DIR = os.path.join(BASE_DIR, 'dist', 'taktik-bot')
BRIDGES_DIR = os.path.join(BASE_DIR, 'bridges')

def get_uiautomator2_assets_path():
    """Get the path to uiautomator2 assets folder"""
    import uiautomator2
    return os.path.join(os.path.dirname(uiautomator2.__file__), 'assets')

def build_desktop_bridge():
    """Build the main desktop_bridge.py as standalone executable"""
    u2_assets = get_uiautomator2_assets_path()
    PyInstaller.__main__.run([
        os.path.join(BRIDGES_DIR, 'instagram', 'desktop_bridge.py'),
        '--name=desktop_bridge',
        '--onefile',
        '--console',  # Keep console for subprocess communication
        f'--distpath={DIST_DIR}',
        f'--workpath={os.path.join(BASE_DIR, "build")}',
        f'--specpath={os.path.join(BASE_DIR, "build")}',
        '--clean',
        # Add hidden imports that PyInstaller might miss
        '--hidden-import=taktik',
        '--hidden-import=taktik.core',
        '--hidden-import=taktik.core.bot',
        '--hidden-import=taktik.core.session_manager',
        '--hidden-import=taktik.core.device_manager',
        '--hidden-import=taktik.actions',
        '--hidden-import=taktik.utils',
        '--hidden-import=adbutils',
        '--hidden-import=uiautomator2',
        '--hidden-import=cv2',
        '--hidden-import=PIL',
        '--hidden-import=yaml',
        '--hidden-import=loguru',
        '--hidden-import=rich',
        '--hidden-import=typer',
        '--hidden-import=pydantic',
        # Add the taktik package
        f'--add-data={os.path.join(BASE_DIR, "taktik")};taktik',
        # Add uiautomator2 assets (u2.jar, apk, etc.)
        f'--add-data={u2_assets};uiautomator2/assets',
    ])

def build_dm_bridge():
    """Build dm_bridge.py as standalone executable"""
    u2_assets = get_uiautomator2_assets_path()
    PyInstaller.__main__.run([
        os.path.join(BRIDGES_DIR, 'instagram', 'dm_bridge.py'),
        '--name=dm_bridge',
        '--onefile',
        '--console',
        f'--distpath={DIST_DIR}',
        f'--workpath={os.path.join(BASE_DIR, "build")}',
        f'--specpath={os.path.join(BASE_DIR, "build")}',
        '--clean',
        '--hidden-import=taktik',
        '--hidden-import=adbutils',
        '--hidden-import=uiautomator2',
        '--hidden-import=PIL',
        '--hidden-import=loguru',
        f'--add-data={os.path.join(BASE_DIR, "taktik")};taktik',
        f'--add-data={u2_assets};uiautomator2/assets',
    ])

def build_scraping_bridge():
    """Build scraping_bridge.py as standalone executable"""
    u2_assets = get_uiautomator2_assets_path()
    PyInstaller.__main__.run([
        os.path.join(BRIDGES_DIR, 'instagram', 'scraping_bridge.py'),
        '--name=scraping_bridge',
        '--onefile',
        '--console',
        f'--distpath={DIST_DIR}',
        f'--workpath={os.path.join(BASE_DIR, "build")}',
        f'--specpath={os.path.join(BASE_DIR, "build")}',
        '--clean',
        '--hidden-import=taktik',
        '--hidden-import=adbutils',
        '--hidden-import=uiautomator2',
        '--hidden-import=PIL',
        '--hidden-import=loguru',
        f'--add-data={os.path.join(BASE_DIR, "taktik")};taktik',
        f'--add-data={u2_assets};uiautomator2/assets',
    ])

def build_cold_dm_bridge():
    """Build cold_dm_bridge.py as standalone executable"""
    u2_assets = get_uiautomator2_assets_path()
    PyInstaller.__main__.run([
        os.path.join(BRIDGES_DIR, 'instagram', 'cold_dm_bridge.py'),
        '--name=cold_dm_bridge',
        '--onefile',
        '--console',
        f'--distpath={DIST_DIR}',
        f'--workpath={os.path.join(BASE_DIR, "build")}',
        f'--specpath={os.path.join(BASE_DIR, "build")}',
        '--clean',
        '--hidden-import=taktik',
        '--hidden-import=adbutils',
        '--hidden-import=uiautomator2',
        '--hidden-import=PIL',
        '--hidden-import=loguru',
        f'--add-data={os.path.join(BASE_DIR, "taktik")};taktik',
        f'--add-data={u2_assets};uiautomator2/assets',
    ])

def build_discovery_bridge():
    """Build discovery_bridge.py as standalone executable"""
    u2_assets = get_uiautomator2_assets_path()
    PyInstaller.__main__.run([
        os.path.join(BRIDGES_DIR, 'instagram', 'discovery_bridge.py'),
        '--name=discovery_bridge',
        '--onefile',
        '--console',
        f'--distpath={DIST_DIR}',
        f'--workpath={os.path.join(BASE_DIR, "build")}',
        f'--specpath={os.path.join(BASE_DIR, "build")}',
        '--clean',
        '--hidden-import=taktik',
        '--hidden-import=adbutils',
        '--hidden-import=uiautomator2',
        '--hidden-import=PIL',
        '--hidden-import=loguru',
        f'--add-data={os.path.join(BASE_DIR, "taktik")};taktik',
        f'--add-data={u2_assets};uiautomator2/assets',
    ])

def build_tiktok_bridge():
    """Build tiktok_bridge.py as standalone executable"""
    u2_assets = get_uiautomator2_assets_path()
    PyInstaller.__main__.run([
        os.path.join(BRIDGES_DIR, 'tiktok', 'tiktok_bridge.py'),
        '--name=tiktok_bridge',
        '--onefile',
        '--console',
        f'--distpath={DIST_DIR}',
        f'--workpath={os.path.join(BASE_DIR, "build")}',
        f'--specpath={os.path.join(BASE_DIR, "build")}',
        '--clean',
        '--hidden-import=taktik',
        '--hidden-import=adbutils',
        '--hidden-import=uiautomator2',
        '--hidden-import=PIL',
        '--hidden-import=loguru',
        '--hidden-import=bridges.tiktok.base',
        '--hidden-import=bridges.tiktok.for_you_bridge',
        '--hidden-import=bridges.tiktok.dm_read_bridge',
        '--hidden-import=bridges.tiktok.dm_send_bridge',
        '--hidden-import=bridges.tiktok.search_bridge',
        '--hidden-import=bridges.tiktok.followers_bridge',
        f'--add-data={os.path.join(BASE_DIR, "taktik")};taktik',
        f'--add-data={os.path.join(BASE_DIR, "bridges")};bridges',
        f'--add-data={u2_assets};uiautomator2/assets',
    ])

def main():
    print("=" * 50)
    print("TAKTIK Bot - Building Executables")
    print("=" * 50)
    
    # Clean previous builds
    if os.path.exists(DIST_DIR):
        print(f"Cleaning {DIST_DIR}...")
        shutil.rmtree(DIST_DIR)
    
    os.makedirs(DIST_DIR, exist_ok=True)
    
    print("\n[1/6] Building desktop_bridge.exe...")
    build_desktop_bridge()
    
    print("\n[2/6] Building dm_bridge.exe...")
    build_dm_bridge()
    
    print("\n[3/6] Building scraping_bridge.exe...")
    build_scraping_bridge()
    
    print("\n[4/6] Building cold_dm_bridge.exe...")
    build_cold_dm_bridge()
    
    print("\n[5/6] Building discovery_bridge.exe...")
    build_discovery_bridge()
    
    print("\n[6/6] Building tiktok_bridge.exe...")
    build_tiktok_bridge()
    
    print("\n" + "=" * 50)
    print("Build complete!")
    print(f"Executables are in: {DIST_DIR}")
    print("=" * 50)

if __name__ == '__main__':
    main()
