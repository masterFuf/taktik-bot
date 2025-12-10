#!/usr/bin/env python3
"""
Proxy Manager for mitmproxy + Frida SSL bypass.
Manages the interception infrastructure for capturing Instagram media.
"""
import os
import sys
import json
import subprocess
import threading
import time
from typing import Optional, Callable, Dict, Any, List
from pathlib import Path
from loguru import logger


class ProxyManager:
    """
    Manages mitmproxy and Frida for SSL interception.
    
    Architecture:
        LDPlayer -> mitmproxy (port 8888) -> Instagram
                        |
                        v (stdout JSON)
                    MediaCaptureService
                        |
                        v (callback)
                    DesktopBridge -> Electron
    """
    
    def __init__(
        self,
        proxy_port: int = 8888,
        device_id: Optional[str] = None,
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.proxy_port = proxy_port
        self.device_id = device_id
        self.on_message = on_message
        
        self.mitm_process: Optional[subprocess.Popen] = None
        self.frida_process: Optional[subprocess.Popen] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Paths
        self.base_dir = Path(__file__).parent.parent.parent.parent
        self.addon_path = self.base_dir / "mitm_addon.py"
        self.frida_script_path = self.base_dir / "frida_ssl_bypass.js"
        
        # Message buffer for recent captures
        self.message_buffer: List[Dict[str, Any]] = []
        self.buffer_max_size = 100
    
    def start(self) -> bool:
        """Start the proxy infrastructure."""
        try:
            # Start mitmproxy
            if not self._start_mitmproxy():
                return False
            
            # Start Frida SSL bypass (if device connected)
            if self.device_id:
                self._start_frida_bypass()
            
            # Configure Android proxy
            if self.device_id:
                self._configure_android_proxy()
            
            self.running = True
            logger.info(f"ProxyManager started on port {self.proxy_port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start ProxyManager: {e}")
            self.stop()
            return False
    
    def _start_mitmproxy(self) -> bool:
        """Start mitmproxy with our addon."""
        try:
            if not self.addon_path.exists():
                logger.error(f"mitm_addon.py not found at {self.addon_path}")
                return False
            
            # Build command
            cmd = [
                sys.executable, "-m", "mitmproxy.tools.main",
                "mitmdump",
                "-s", str(self.addon_path),
                "-p", str(self.proxy_port),
                "--quiet",
                "--set", "stream_large_bodies=1m",  # Stream large files
                "--set", "keep_host_header=true"
            ]
            
            # Alternative: use mitmdump directly if installed
            try:
                # Check if mitmdump is available
                result = subprocess.run(["mitmdump", "--version"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    cmd = [
                        "mitmdump",
                        "-s", str(self.addon_path),
                        "-p", str(self.proxy_port),
                        "--quiet"
                    ]
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            
            logger.info(f"Starting mitmproxy: {' '.join(cmd)}")
            
            self.mitm_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # Start reader thread
            self.reader_thread = threading.Thread(target=self._read_mitm_output, daemon=True)
            self.reader_thread.start()
            
            # Wait a bit and check if process is still running
            time.sleep(1)
            if self.mitm_process.poll() is not None:
                stderr = self.mitm_process.stderr.read()
                logger.error(f"mitmproxy failed to start: {stderr}")
                return False
            
            logger.info("mitmproxy started successfully")
            return True
            
        except FileNotFoundError:
            logger.error("mitmproxy not installed. Run: pip install mitmproxy")
            return False
        except Exception as e:
            logger.error(f"Failed to start mitmproxy: {e}")
            return False
    
    def _read_mitm_output(self):
        """Read and process mitmproxy stdout."""
        while self.running and self.mitm_process:
            try:
                line = self.mitm_process.stdout.readline()
                if not line:
                    if self.mitm_process.poll() is not None:
                        break
                    continue
                
                line = line.strip()
                if not line:
                    continue
                
                try:
                    message = json.loads(line)
                    self._handle_message(message)
                except json.JSONDecodeError:
                    # Not JSON, might be mitmproxy log
                    logger.debug(f"mitmproxy: {line}")
                    
            except Exception as e:
                logger.error(f"Error reading mitmproxy output: {e}")
    
    def _handle_message(self, message: Dict[str, Any]):
        """Handle a message from mitmproxy addon."""
        msg_type = message.get("type")
        
        # Add to buffer
        self.message_buffer.append(message)
        if len(self.message_buffer) > self.buffer_max_size:
            self.message_buffer.pop(0)
        
        # Log based on type
        if msg_type == "profile_data":
            username = message.get("username", "unknown")
            followers = message.get("follower_count", 0)
            logger.info(f"📸 Captured profile: @{username} ({followers} followers)")
        elif msg_type == "media_data":
            username = message.get("username", "unknown")
            likes = message.get("like_count", 0)
            logger.info(f"🖼️ Captured media from @{username} ({likes} likes)")
        elif msg_type == "cdn_capture":
            image_type = message.get("image_type", "unknown")
            size_kb = message.get("size", 0) / 1024
            logger.debug(f"📥 CDN capture: {image_type} ({size_kb:.1f}KB)")
        
        # Forward to callback
        if self.on_message:
            try:
                self.on_message(message)
            except Exception as e:
                logger.error(f"Error in message callback: {e}")
    
    def _start_frida_bypass(self) -> bool:
        """Start Frida SSL bypass script."""
        try:
            if not self.frida_script_path.exists():
                logger.warning(f"Frida script not found at {self.frida_script_path}")
                return False
            
            # Check if frida is installed
            try:
                subprocess.run(["frida", "--version"], capture_output=True, timeout=5)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.warning("Frida not installed. Run: pip install frida-tools")
                return False
            
            # Build command - attach to running Instagram
            cmd = [
                "frida",
                "-U",  # USB device
                "-n", "Instagram",  # Process name
                "-l", str(self.frida_script_path),
                "--no-pause"
            ]
            
            if self.device_id:
                cmd.extend(["-D", self.device_id])
            
            logger.info(f"Starting Frida: {' '.join(cmd)}")
            
            self.frida_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # Start a thread to log Frida output
            def read_frida():
                while self.running and self.frida_process:
                    line = self.frida_process.stdout.readline()
                    if line:
                        logger.debug(f"Frida: {line.strip()}")
                    elif self.frida_process.poll() is not None:
                        break
            
            threading.Thread(target=read_frida, daemon=True).start()
            
            logger.info("Frida SSL bypass started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Frida: {e}")
            return False
    
    def _configure_android_proxy(self) -> bool:
        """Configure Android emulator to use our proxy."""
        try:
            # Get host IP (for emulator, use 10.0.2.2 which maps to host)
            proxy_host = "10.0.2.2"  # Android emulator host loopback
            
            # For LDPlayer, might need actual host IP
            # proxy_host = "192.168.x.x"
            
            cmd_base = ["adb"]
            if self.device_id:
                cmd_base.extend(["-s", self.device_id])
            
            # Set global HTTP proxy
            subprocess.run(
                cmd_base + ["shell", "settings", "put", "global", "http_proxy", f"{proxy_host}:{self.proxy_port}"],
                capture_output=True,
                timeout=10
            )
            
            logger.info(f"Android proxy configured: {proxy_host}:{self.proxy_port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure Android proxy: {e}")
            return False
    
    def _clear_android_proxy(self) -> bool:
        """Clear Android proxy settings."""
        try:
            cmd_base = ["adb"]
            if self.device_id:
                cmd_base.extend(["-s", self.device_id])
            
            subprocess.run(
                cmd_base + ["shell", "settings", "put", "global", "http_proxy", ":0"],
                capture_output=True,
                timeout=10
            )
            
            logger.info("Android proxy cleared")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear Android proxy: {e}")
            return False
    
    def get_recent_captures(self, msg_type: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent captured messages."""
        messages = self.message_buffer
        
        if msg_type:
            messages = [m for m in messages if m.get("type") == msg_type]
        
        return messages[-limit:]
    
    def get_profile_data(self, username: str) -> Optional[Dict[str, Any]]:
        """Get captured profile data for a username."""
        for msg in reversed(self.message_buffer):
            if msg.get("type") == "profile_data" and msg.get("username") == username:
                return msg
        return None
    
    def stop(self):
        """Stop all proxy infrastructure."""
        self.running = False
        
        # Clear Android proxy first
        if self.device_id:
            self._clear_android_proxy()
        
        # Stop Frida
        if self.frida_process:
            try:
                self.frida_process.terminate()
                self.frida_process.wait(timeout=5)
            except:
                self.frida_process.kill()
            self.frida_process = None
        
        # Stop mitmproxy
        if self.mitm_process:
            try:
                self.mitm_process.terminate()
                self.mitm_process.wait(timeout=5)
            except:
                self.mitm_process.kill()
            self.mitm_process = None
        
        logger.info("ProxyManager stopped")
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
