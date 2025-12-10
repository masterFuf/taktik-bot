#!/usr/bin/env python3
"""
Media Capture Service for Instagram.
Provides a high-level interface for capturing and forwarding Instagram media data.
"""
import json
import threading
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime
from loguru import logger

from .proxy_manager import ProxyManager


@dataclass
class ProfileCapture:
    """Captured Instagram profile data."""
    username: str
    full_name: Optional[str] = None
    biography: Optional[str] = None
    profile_pic_url: Optional[str] = None
    profile_pic_url_hd: Optional[str] = None
    follower_count: int = 0
    following_count: int = 0
    media_count: int = 0
    is_private: bool = False
    is_verified: bool = False
    is_business: bool = False
    external_url: Optional[str] = None
    category: Optional[str] = None
    captured_at: str = ""
    
    def __post_init__(self):
        if not self.captured_at:
            self.captured_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MediaCapture:
    """Captured Instagram media data."""
    media_id: str
    media_type: str  # photo, video, carousel
    image_url: str
    width: int = 0
    height: int = 0
    like_count: int = 0
    comment_count: int = 0
    caption: str = ""
    taken_at: Optional[int] = None
    username: Optional[str] = None
    captured_at: str = ""
    
    def __post_init__(self):
        if not self.captured_at:
            self.captured_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MediaCaptureService:
    """
    High-level service for capturing Instagram media.
    
    Usage:
        service = MediaCaptureService(device_id="emulator-5554")
        service.on_profile_captured = lambda p: print(f"Got profile: {p.username}")
        service.on_media_captured = lambda m: print(f"Got media: {m.media_id}")
        
        service.start()
        # ... bot runs and visits profiles ...
        service.stop()
    """
    
    def __init__(
        self,
        device_id: Optional[str] = None,
        proxy_port: int = 8888,
        desktop_bridge_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ):
        self.device_id = device_id
        self.proxy_port = proxy_port
        self.desktop_bridge_callback = desktop_bridge_callback
        
        self.proxy_manager: Optional[ProxyManager] = None
        self.running = False
        
        # Captured data storage
        self.profiles: Dict[str, ProfileCapture] = {}
        self.media: Dict[str, MediaCapture] = {}
        
        # Callbacks
        self.on_profile_captured: Optional[Callable[[ProfileCapture], None]] = None
        self.on_media_captured: Optional[Callable[[MediaCapture], None]] = None
        self.on_cdn_captured: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # Lock for thread safety
        self._lock = threading.Lock()
    
    def start(self) -> bool:
        """Start the media capture service."""
        try:
            self.proxy_manager = ProxyManager(
                proxy_port=self.proxy_port,
                device_id=self.device_id,
                on_message=self._handle_proxy_message
            )
            
            if not self.proxy_manager.start():
                logger.error("Failed to start ProxyManager")
                return False
            
            self.running = True
            logger.info("MediaCaptureService started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MediaCaptureService: {e}")
            return False
    
    def _handle_proxy_message(self, message: Dict[str, Any]):
        """Handle messages from the proxy."""
        msg_type = message.get("type")
        
        try:
            if msg_type == "profile_data":
                self._handle_profile_data(message)
            elif msg_type == "media_data":
                self._handle_media_data(message)
            elif msg_type == "cdn_capture":
                self._handle_cdn_capture(message)
            elif msg_type == "carousel_media":
                self._handle_carousel_media(message)
                
        except Exception as e:
            logger.error(f"Error handling proxy message: {e}")
    
    def _handle_profile_data(self, data: Dict[str, Any]):
        """Handle captured profile data."""
        try:
            profile = ProfileCapture(
                username=data.get("username", ""),
                full_name=data.get("full_name"),
                biography=data.get("biography"),
                profile_pic_url=data.get("profile_pic_url"),
                profile_pic_url_hd=data.get("profile_pic_url_hd"),
                follower_count=data.get("follower_count", 0),
                following_count=data.get("following_count", 0),
                media_count=data.get("media_count", 0),
                is_private=data.get("is_private", False),
                is_verified=data.get("is_verified", False),
                is_business=data.get("is_business", False),
                external_url=data.get("external_url"),
                category=data.get("category")
            )
            
            with self._lock:
                self.profiles[profile.username] = profile
            
            # Trigger callback
            if self.on_profile_captured:
                self.on_profile_captured(profile)
            
            # Forward to desktop bridge
            self._send_to_desktop("profile_captured", profile.to_dict())
            
            logger.info(f"📸 Profile captured: @{profile.username}")
            
        except Exception as e:
            logger.error(f"Error handling profile data: {e}")
    
    def _handle_media_data(self, data: Dict[str, Any]):
        """Handle captured media data."""
        try:
            media = MediaCapture(
                media_id=data.get("media_id", ""),
                media_type=data.get("media_type", "photo"),
                image_url=data.get("image_url", ""),
                width=data.get("width", 0),
                height=data.get("height", 0),
                like_count=data.get("like_count", 0),
                comment_count=data.get("comment_count", 0),
                caption=data.get("caption", ""),
                taken_at=data.get("taken_at"),
                username=data.get("username")
            )
            
            with self._lock:
                self.media[media.media_id] = media
            
            # Trigger callback
            if self.on_media_captured:
                self.on_media_captured(media)
            
            # Forward to desktop bridge
            self._send_to_desktop("media_captured", media.to_dict())
            
            logger.debug(f"🖼️ Media captured: {media.media_id}")
            
        except Exception as e:
            logger.error(f"Error handling media data: {e}")
    
    def _handle_cdn_capture(self, data: Dict[str, Any]):
        """Handle CDN URL capture."""
        try:
            # Trigger callback
            if self.on_cdn_captured:
                self.on_cdn_captured(data)
            
            # Forward to desktop bridge
            self._send_to_desktop("cdn_captured", data)
            
        except Exception as e:
            logger.error(f"Error handling CDN capture: {e}")
    
    def _handle_carousel_media(self, data: Dict[str, Any]):
        """Handle carousel media items."""
        # Forward as media capture
        self._send_to_desktop("carousel_captured", data)
    
    def _send_to_desktop(self, event_type: str, data: Dict[str, Any]):
        """Send data to desktop bridge."""
        if self.desktop_bridge_callback:
            try:
                self.desktop_bridge_callback(event_type, data)
            except Exception as e:
                logger.error(f"Error sending to desktop: {e}")
        else:
            # Fallback: print JSON to stdout for desktop bridge
            message = {"type": event_type, **data}
            print(json.dumps(message), flush=True)
    
    def get_profile(self, username: str) -> Optional[ProfileCapture]:
        """Get captured profile data for a username."""
        with self._lock:
            return self.profiles.get(username)
    
    def get_all_profiles(self) -> List[ProfileCapture]:
        """Get all captured profiles."""
        with self._lock:
            return list(self.profiles.values())
    
    def get_media(self, media_id: str) -> Optional[MediaCapture]:
        """Get captured media by ID."""
        with self._lock:
            return self.media.get(media_id)
    
    def get_media_by_username(self, username: str) -> List[MediaCapture]:
        """Get all captured media for a username."""
        with self._lock:
            return [m for m in self.media.values() if m.username == username]
    
    def get_stats(self) -> Dict[str, int]:
        """Get capture statistics."""
        with self._lock:
            return {
                "profiles_captured": len(self.profiles),
                "media_captured": len(self.media),
                "total_followers": sum(p.follower_count for p in self.profiles.values()),
                "total_likes": sum(m.like_count for m in self.media.values())
            }
    
    def clear(self):
        """Clear all captured data."""
        with self._lock:
            self.profiles.clear()
            self.media.clear()
    
    def stop(self):
        """Stop the media capture service."""
        self.running = False
        
        if self.proxy_manager:
            self.proxy_manager.stop()
            self.proxy_manager = None
        
        logger.info("MediaCaptureService stopped")
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
