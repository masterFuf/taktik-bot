#!/usr/bin/env python3
"""
Setup script for media capture infrastructure.
Installs mitmproxy, Frida, and configures the Android emulator.

Usage:
    python scripts/setup_media_capture.py --device-id emulator-5554
"""
import os
import sys
import subprocess
import argparse
import shutil
from pathlib import Path


def run_cmd(cmd: list, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a command and optionally check for errors."""
    print(f"  → {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def check_python_packages():
    """Check and install required Python packages."""
    print("\n📦 Checking Python packages...")
    
    packages = [
        ("mitmproxy", "mitmproxy"),
        ("frida", "frida-tools"),
    ]
    
    for import_name, pip_name in packages:
        try:
            __import__(import_name)
            print(f"  ✅ {pip_name} is installed")
        except ImportError:
            print(f"  ⬇️ Installing {pip_name}...")
            run_cmd([sys.executable, "-m", "pip", "install", pip_name])


def check_adb():
    """Check if ADB is available."""
    print("\n🔧 Checking ADB...")
    
    try:
        result = run_cmd(["adb", "version"], capture=True)
        print(f"  ✅ ADB found: {result.stdout.split(chr(10))[0]}")
        return True
    except FileNotFoundError:
        print("  ❌ ADB not found. Please install Android SDK Platform Tools.")
        return False


def list_devices():
    """List connected Android devices."""
    print("\n📱 Connected devices:")
    
    result = run_cmd(["adb", "devices", "-l"], capture=True)
    lines = result.stdout.strip().split('\n')[1:]  # Skip header
    
    devices = []
    for line in lines:
        if line.strip():
            parts = line.split()
            device_id = parts[0]
            status = parts[1] if len(parts) > 1 else "unknown"
            devices.append((device_id, status))
            print(f"  • {device_id} ({status})")
    
    return devices


def generate_mitmproxy_cert():
    """Generate mitmproxy CA certificate."""
    print("\n🔐 Generating mitmproxy certificate...")
    
    # mitmproxy generates certs on first run
    mitmproxy_dir = Path.home() / ".mitmproxy"
    cert_path = mitmproxy_dir / "mitmproxy-ca-cert.cer"
    
    if cert_path.exists():
        print(f"  ✅ Certificate already exists: {cert_path}")
        return cert_path
    
    print("  ⏳ Running mitmproxy to generate certificate...")
    
    # Run mitmdump briefly to generate certs
    try:
        proc = subprocess.Popen(
            ["mitmdump", "-p", "18888"],  # Use different port to avoid conflicts
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        import time
        time.sleep(3)
        proc.terminate()
        proc.wait(timeout=5)
    except Exception as e:
        print(f"  ⚠️ Error running mitmdump: {e}")
    
    if cert_path.exists():
        print(f"  ✅ Certificate generated: {cert_path}")
        return cert_path
    else:
        print("  ❌ Failed to generate certificate")
        return None


def push_cert_to_device(device_id: str, cert_path: Path):
    """Push mitmproxy certificate to Android device."""
    print(f"\n📲 Pushing certificate to {device_id}...")
    
    # Push to sdcard
    run_cmd(["adb", "-s", device_id, "push", str(cert_path), "/sdcard/mitmproxy-ca-cert.cer"])
    print("  ✅ Certificate pushed to /sdcard/mitmproxy-ca-cert.cer")
    
    print("\n  ⚠️ MANUAL STEP REQUIRED:")
    print("  1. On the Android device, go to Settings > Security")
    print("  2. Select 'Install from storage' or 'Install certificates'")
    print("  3. Navigate to /sdcard/ and select mitmproxy-ca-cert.cer")
    print("  4. Name it 'mitmproxy' and select 'VPN and apps'")


def install_frida_server(device_id: str):
    """Download and install frida-server on Android device."""
    print(f"\n🔧 Setting up Frida server on {device_id}...")
    
    # Check device architecture
    result = run_cmd(["adb", "-s", device_id, "shell", "getprop", "ro.product.cpu.abi"], capture=True)
    arch = result.stdout.strip()
    print(f"  Device architecture: {arch}")
    
    # Map architecture to frida-server binary name
    arch_map = {
        "arm64-v8a": "arm64",
        "armeabi-v7a": "arm",
        "x86_64": "x86_64",
        "x86": "x86"
    }
    
    frida_arch = arch_map.get(arch, "arm64")
    
    # Check frida version
    try:
        import frida
        frida_version = frida.__version__
        print(f"  Frida version: {frida_version}")
    except ImportError:
        print("  ❌ Frida not installed. Run: pip install frida-tools")
        return False
    
    # Download URL
    download_url = f"https://github.com/frida/frida/releases/download/{frida_version}/frida-server-{frida_version}-android-{frida_arch}.xz"
    
    print(f"\n  ⚠️ MANUAL STEP REQUIRED:")
    print(f"  1. Download frida-server from:")
    print(f"     {download_url}")
    print(f"  2. Extract the .xz file")
    print(f"  3. Push to device:")
    print(f"     adb -s {device_id} push frida-server /data/local/tmp/")
    print(f"  4. Make executable:")
    print(f"     adb -s {device_id} shell chmod 755 /data/local/tmp/frida-server")
    print(f"  5. Run as root:")
    print(f"     adb -s {device_id} shell su -c '/data/local/tmp/frida-server &'")
    
    return True


def configure_proxy(device_id: str, proxy_host: str = "10.0.2.2", proxy_port: int = 8888):
    """Configure Android device to use proxy."""
    print(f"\n🌐 Configuring proxy on {device_id}...")
    
    # For emulators, 10.0.2.2 is the host machine
    # For physical devices or LDPlayer, use actual host IP
    
    run_cmd([
        "adb", "-s", device_id, "shell",
        "settings", "put", "global", "http_proxy", f"{proxy_host}:{proxy_port}"
    ])
    
    print(f"  ✅ Proxy configured: {proxy_host}:{proxy_port}")
    print("\n  💡 To clear proxy later:")
    print(f"     adb -s {device_id} shell settings put global http_proxy :0")


def create_test_script():
    """Create a test script to verify the setup."""
    print("\n📝 Creating test script...")
    
    test_script = Path(__file__).parent.parent / "test_media_capture.py"
    
    content = '''#!/usr/bin/env python3
"""Test script for media capture setup."""
import time
from taktik.core.social_media.instagram.media import MediaCaptureService

def main():
    print("🧪 Testing Media Capture Service...")
    
    # Create service
    service = MediaCaptureService(
        device_id=None,  # Set your device ID
        proxy_port=8888
    )
    
    # Set up callbacks
    def on_profile(profile):
        print(f"📸 Profile: @{profile.username} - {profile.follower_count} followers")
        print(f"   Profile pic: {profile.profile_pic_url}")
    
    def on_media(media):
        print(f"🖼️ Media: {media.media_id} - {media.like_count} likes")
        print(f"   Image: {media.image_url}")
    
    service.on_profile_captured = on_profile
    service.on_media_captured = on_media
    
    # Start service
    print("Starting service...")
    if not service.start():
        print("❌ Failed to start service")
        return
    
    print("✅ Service started. Waiting for captures...")
    print("   Open Instagram on the device and browse profiles.")
    print("   Press Ctrl+C to stop.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\\nStopping...")
    
    # Print stats
    stats = service.get_stats()
    print(f"\\n📊 Final stats: {stats}")
    
    service.stop()
    print("✅ Done")

if __name__ == "__main__":
    main()
'''
    
    test_script.write_text(content)
    print(f"  ✅ Created: {test_script}")


def main():
    parser = argparse.ArgumentParser(description="Setup media capture infrastructure")
    parser.add_argument("--device-id", "-d", help="Android device ID")
    parser.add_argument("--proxy-port", "-p", type=int, default=8888, help="Proxy port (default: 8888)")
    parser.add_argument("--skip-packages", action="store_true", help="Skip Python package installation")
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 TAKTIK Media Capture Setup")
    print("=" * 60)
    
    # Check Python packages
    if not args.skip_packages:
        check_python_packages()
    
    # Check ADB
    if not check_adb():
        print("\n❌ Setup incomplete. Please install ADB first.")
        return 1
    
    # List devices
    devices = list_devices()
    
    if not devices:
        print("\n⚠️ No devices connected. Connect a device and try again.")
        return 1
    
    # Select device
    device_id = args.device_id
    if not device_id:
        if len(devices) == 1:
            device_id = devices[0][0]
            print(f"\n  Using device: {device_id}")
        else:
            print("\n  Multiple devices found. Please specify with --device-id")
            return 1
    
    # Generate mitmproxy certificate
    cert_path = generate_mitmproxy_cert()
    
    if cert_path:
        # Push certificate to device
        push_cert_to_device(device_id, cert_path)
    
    # Setup Frida
    install_frida_server(device_id)
    
    # Configure proxy
    configure_proxy(device_id, proxy_port=args.proxy_port)
    
    # Create test script
    create_test_script()
    
    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print("=" * 60)
    print("\n📋 Next steps:")
    print("  1. Install the mitmproxy certificate on the device (see above)")
    print("  2. Install and run frida-server on the device (see above)")
    print("  3. Test with: python test_media_capture.py")
    print("  4. Run a bot session with mediaCaptureEnabled: true")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
