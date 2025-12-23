"""
Build script to create standalone Python executables for TAKTIK Bot
Run with: python build_exe.py
"""

import PyInstaller.__main__
import os
import shutil

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, 'dist', 'taktik-bot')

def get_uiautomator2_assets_path():
    """Get the path to uiautomator2 assets folder"""
    import uiautomator2
    return os.path.join(os.path.dirname(uiautomator2.__file__), 'assets')

def build_desktop_bridge():
    """Build the main desktop_bridge.py as standalone executable"""
    u2_assets = get_uiautomator2_assets_path()
    PyInstaller.__main__.run([
        os.path.join(BASE_DIR, 'desktop_bridge.py'),
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
        os.path.join(BASE_DIR, 'dm_bridge.py'),
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
        os.path.join(BASE_DIR, 'scraping_bridge.py'),
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

def main():
    print("=" * 50)
    print("TAKTIK Bot - Building Executables")
    print("=" * 50)
    
    # Clean previous builds
    if os.path.exists(DIST_DIR):
        print(f"Cleaning {DIST_DIR}...")
        shutil.rmtree(DIST_DIR)
    
    os.makedirs(DIST_DIR, exist_ok=True)
    
    print("\n[1/3] Building desktop_bridge.exe...")
    build_desktop_bridge()
    
    print("\n[2/3] Building dm_bridge.exe...")
    build_dm_bridge()
    
    print("\n[3/3] Building scraping_bridge.exe...")
    build_scraping_bridge()
    
    print("\n" + "=" * 50)
    print("Build complete!")
    print(f"Executables are in: {DIST_DIR}")
    print("=" * 50)

if __name__ == '__main__':
    main()
