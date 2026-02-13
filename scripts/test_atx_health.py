#!/usr/bin/env python3
"""
Script de test pour diagnostiquer les problèmes ATX/uiautomator2.

Ce script permet de:
1. Vérifier l'état de santé de l'agent ATX
2. Reproduire le bug "Instagram not installed" 
3. Tester la réparation automatique ATX

Usage:
    python test_atx_health.py [device_id]
    python test_atx_health.py --simulate-failure [device_id]
    python test_atx_health.py --kill-atx [device_id]
    python test_atx_health.py --uninstall-atx [device_id]
"""

import sys
import os
import subprocess
import argparse
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from taktik.core.social_media.instagram.actions.core.device import DeviceManager


def get_device_id(args_device_id: str = None) -> str:
    """Get device ID from args or auto-detect."""
    if args_device_id:
        return args_device_id
    
    devices = DeviceManager.list_devices()
    if not devices:
        print("❌ No devices connected")
        sys.exit(1)
    
    device_id = devices[0]["id"]
    print(f"📱 Using device: {device_id}")
    return device_id


def check_atx_health(device_id: str):
    """Check ATX health and display detailed status."""
    print("\n" + "="*60)
    print("🔍 ATX HEALTH CHECK")
    print("="*60)
    
    dm = DeviceManager(device_id)
    
    # Try to connect (this will trigger ATX verification)
    print("\n1. Attempting connection with ATX verification...")
    connected = dm.connect(verify_atx=True)
    
    if connected:
        print("   ✅ Connection successful with ATX verification")
    else:
        print("   ❌ Connection failed")
    
    # Get detailed status
    print("\n2. Getting detailed ATX status...")
    status = dm.get_atx_status()
    
    print(f"\n   Device ID: {status['device_id']}")
    print(f"   Connected: {status['connected']}")
    print(f"   ATX Verified: {status['atx_verified']}")
    print(f"   ATX Healthy: {status['atx_healthy']}")
    print(f"   ATX Packages: {status['atx_packages_installed']}")
    if status['error']:
        print(f"   Error: {status['error']}")
    
    # Test app_info (the method that was failing)
    print("\n3. Testing app_info() method (the one that was failing)...")
    try:
        if dm.device:
            info = dm.device.app_info("com.instagram.android")
            if info:
                print(f"   ✅ app_info() works - Instagram version: {info.get('versionName', 'unknown')}")
            else:
                print("   ⚠️ app_info() returned None (Instagram not installed or ATX issue)")
        else:
            print("   ❌ Device not connected")
    except Exception as e:
        print(f"   ❌ app_info() failed: {e}")
    
    # Test with ADB fallback
    print("\n4. Testing ADB fallback method...")
    installed_adb = dm._is_app_installed_adb("com.instagram.android")
    print(f"   ADB check: Instagram installed = {installed_adb}")
    
    return status


def kill_atx(device_id: str):
    """Kill ATX processes to simulate failure."""
    print("\n" + "="*60)
    print("💀 KILLING ATX PROCESSES")
    print("="*60)
    
    commands = [
        ["adb", "-s", device_id, "shell", "pkill", "-f", "uiautomator"],
        ["adb", "-s", device_id, "shell", "am", "force-stop", "com.github.uiautomator"],
        ["adb", "-s", device_id, "shell", "am", "force-stop", "com.github.uiautomator.test"],
    ]
    
    for cmd in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            print(f"   Executed: {' '.join(cmd[3:])}")
        except Exception as e:
            print(f"   Failed: {e}")
    
    print("\n   ⚠️ ATX processes killed. The next connection attempt should trigger auto-repair.")


def uninstall_atx(device_id: str):
    """Uninstall ATX packages to simulate fresh device."""
    print("\n" + "="*60)
    print("🗑️ UNINSTALLING ATX PACKAGES")
    print("="*60)
    
    packages = [
        "com.github.uiautomator",
        "com.github.uiautomator.test"
    ]
    
    for pkg in packages:
        try:
            result = subprocess.run(
                ["adb", "-s", device_id, "uninstall", pkg],
                capture_output=True, text=True, timeout=30
            )
            if "Success" in result.stdout:
                print(f"   ✅ Uninstalled: {pkg}")
            else:
                print(f"   ⚠️ {pkg}: {result.stdout.strip()}")
        except Exception as e:
            print(f"   ❌ Failed to uninstall {pkg}: {e}")
    
    print("\n   ⚠️ ATX packages uninstalled. The next connection will reinstall them.")


def test_repair(device_id: str):
    """Test the auto-repair functionality."""
    print("\n" + "="*60)
    print("🔧 TESTING AUTO-REPAIR")
    print("="*60)
    
    # First kill ATX
    kill_atx(device_id)
    time.sleep(2)
    
    # Now try to connect - should trigger repair
    print("\n   Attempting connection (should trigger auto-repair)...")
    dm = DeviceManager(device_id)
    connected = dm.connect(verify_atx=True)
    
    if connected:
        print("   ✅ Auto-repair successful!")
        status = dm.get_atx_status()
        print(f"   ATX Healthy: {status['atx_healthy']}")
    else:
        print("   ❌ Auto-repair failed")


def simulate_user_bug(device_id: str):
    """Simulate the exact bug the user experienced."""
    print("\n" + "="*60)
    print("🐛 SIMULATING USER BUG SCENARIO")
    print("="*60)
    
    print("\nScenario: Instagram is installed but bot says it's not")
    print("-" * 40)
    
    # Step 1: Check with ADB (like Device Management does)
    print("\n1. Checking with ADB (Device Management method)...")
    result = subprocess.run(
        ["adb", "-s", device_id, "shell", "pm", "list", "packages", "com.instagram.android"],
        capture_output=True, text=True, timeout=10
    )
    adb_installed = "com.instagram.android" in result.stdout
    print(f"   ADB says: Instagram installed = {adb_installed}")
    
    # Step 2: Kill ATX to simulate the bug
    print("\n2. Killing ATX to simulate unhealthy state...")
    kill_atx(device_id)
    time.sleep(1)
    
    # Step 3: Try with uiautomator2 (like old bot code did)
    print("\n3. Checking with uiautomator2 (old bot method)...")
    import uiautomator2 as u2
    try:
        device = u2.connect(device_id)
        info = device.app_info("com.instagram.android")
        if info:
            print(f"   uiautomator2 says: Instagram installed = True")
        else:
            print(f"   uiautomator2 says: Instagram installed = False (BUG REPRODUCED!)")
    except Exception as e:
        print(f"   uiautomator2 FAILED: {e} (BUG REPRODUCED!)")
    
    # Step 4: Now test with new code (with ATX verification and repair)
    print("\n4. Testing with NEW code (ATX verification + repair)...")
    dm = DeviceManager(device_id)
    dm._atx_verified = False  # Reset verification flag
    connected = dm.connect(verify_atx=True)
    
    if connected:
        installed = dm.is_app_installed("com.instagram.android")
        print(f"   New code says: Instagram installed = {installed}")
        if installed:
            print("   ✅ BUG FIXED! New code correctly detects Instagram")
    else:
        print("   ❌ Connection failed even with new code")


def main():
    parser = argparse.ArgumentParser(description="Test ATX/uiautomator2 health")
    parser.add_argument("device_id", nargs="?", help="Device ID (optional, auto-detects)")
    parser.add_argument("--kill-atx", action="store_true", help="Kill ATX processes")
    parser.add_argument("--uninstall-atx", action="store_true", help="Uninstall ATX packages")
    parser.add_argument("--test-repair", action="store_true", help="Test auto-repair")
    parser.add_argument("--simulate-bug", action="store_true", help="Simulate the user's bug")
    
    args = parser.parse_args()
    device_id = get_device_id(args.device_id)
    
    if args.kill_atx:
        kill_atx(device_id)
    elif args.uninstall_atx:
        uninstall_atx(device_id)
    elif args.test_repair:
        test_repair(device_id)
    elif args.simulate_bug:
        simulate_user_bug(device_id)
    else:
        # Default: just check health
        check_atx_health(device_id)
    
    print("\n" + "="*60)
    print("Done!")
    print("="*60)


if __name__ == "__main__":
    main()
