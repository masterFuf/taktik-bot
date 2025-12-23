#!/usr/bin/env python3
"""
mitmproxy addon to capture Instagram CDN URLs and media.
Run with: mitmdump -s mitm_addon.py -p 8888 --quiet

This addon intercepts Instagram API responses and CDN image requests,
forwarding relevant data to the desktop bridge via stdout JSON messages.
"""
import json
import re
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from mitmproxy import http, ctx


class InstagramCDNCapture:
    """Capture Instagram profile pics, post images, and API data."""
    
    # CDN patterns for Instagram media
    CDN_PATTERNS = [
        r'scontent.*\.cdninstagram\.com',
        r'scontent.*\.fbcdn\.net',
        r'instagram.*\.fbcdn\.net',
    ]
    
    # API endpoints to intercept
    API_PATTERNS = [
        r'i\.instagram\.com/api/v1/users/.*/info',  # User info
        r'i\.instagram\.com/api/v1/feed/user/',      # User feed
        r'i\.instagram\.com/api/v1/friendships/',    # Follow status
        r'i\.instagram\.com/api/v1/media/.*/info',   # Media info
    ]
    
    def __init__(self):
        self.captured_media = {}
        self.current_profile = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _send_message(self, msg_type: str, **kwargs):
        """Send JSON message to stdout for desktop bridge."""
        message = {
            "type": msg_type,
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            **kwargs
        }
        print(json.dumps(message), flush=True)
    
    def _is_cdn_url(self, url: str) -> bool:
        """Check if URL is an Instagram CDN URL."""
        return any(re.search(p, url) for p in self.CDN_PATTERNS)
    
    def _is_api_url(self, url: str) -> bool:
        """Check if URL is an Instagram API endpoint."""
        return any(re.search(p, url) for p in self.API_PATTERNS)
    
    def _detect_image_type(self, url: str, content_length: int = 0) -> str:
        """Detect the type of image based on URL patterns."""
        url_lower = url.lower()
        
        # Profile pictures (usually small, specific sizes)
        if any(size in url for size in ['/s150x150/', '/s320x320/', '/s640x640/']):
            return 'profile_pic'
        
        # Story media
        if '/stories/' in url_lower or 'story' in url_lower:
            return 'story'
        
        # Reel thumbnails
        if '/reel/' in url_lower or 'reel' in url_lower:
            return 'reel_thumbnail'
        
        # Post images (larger files, specific patterns)
        if '/p/' in url or content_length > 100000:  # > 100KB likely a post
            return 'post_image'
        
        # Feed images
        if '/e35/' in url or '/e15/' in url:
            return 'feed_image'
        
        return 'unknown'
    
    def _extract_username_from_url(self, url: str) -> Optional[str]:
        """Try to extract username context from URL or recent API calls."""
        # This will be enriched by API response parsing
        return self.current_profile
    
    def _hash_url(self, url: str) -> str:
        """Create a short hash for deduplication."""
        return hashlib.md5(url.encode()).hexdigest()[:12]
    
    def response(self, flow: http.HTTPFlow):
        """Process HTTP responses."""
        url = flow.request.pretty_url
        
        # Handle API responses (user info, media info)
        if self._is_api_url(url):
            self._handle_api_response(flow)
            return
        
        # Handle CDN media
        if self._is_cdn_url(url):
            self._handle_cdn_response(flow)
            return
    
    def _handle_api_response(self, flow: http.HTTPFlow):
        """Parse Instagram API responses for profile/media data."""
        try:
            url = flow.request.pretty_url
            content_type = flow.response.headers.get('content-type', '')
            
            if 'application/json' not in content_type:
                return
            
            data = json.loads(flow.response.content)
            
            # User info endpoint
            if '/users/' in url and '/info' in url:
                user_data = data.get('user', {})
                if user_data:
                    self.current_profile = user_data.get('username')
                    
                    self._send_message(
                        "profile_data",
                        username=user_data.get('username'),
                        full_name=user_data.get('full_name'),
                        biography=user_data.get('biography'),
                        profile_pic_url=user_data.get('profile_pic_url'),
                        profile_pic_url_hd=user_data.get('hd_profile_pic_url_info', {}).get('url'),
                        follower_count=user_data.get('follower_count'),
                        following_count=user_data.get('following_count'),
                        media_count=user_data.get('media_count'),
                        is_private=user_data.get('is_private', False),
                        is_verified=user_data.get('is_verified', False),
                        is_business=user_data.get('is_business', False),
                        external_url=user_data.get('external_url'),
                        category=user_data.get('category')
                    )
            
            # Media info endpoint
            elif '/media/' in url and '/info' in url:
                items = data.get('items', [])
                for item in items:
                    self._parse_media_item(item)
            
            # User feed endpoint
            elif '/feed/user/' in url:
                items = data.get('items', [])
                for item in items[:5]:  # Limit to first 5 posts
                    self._parse_media_item(item)
                    
        except json.JSONDecodeError:
            pass
        except Exception as e:
            ctx.log.error(f"API parse error: {e}")
    
    def _parse_media_item(self, item: Dict[str, Any]):
        """Parse a media item from Instagram API."""
        try:
            media_type = item.get('media_type')  # 1=photo, 2=video, 8=carousel
            
            # Get image candidates
            image_versions = item.get('image_versions2', {})
            candidates = image_versions.get('candidates', [])
            
            if candidates:
                # Get highest quality image
                best_image = max(candidates, key=lambda x: x.get('width', 0) * x.get('height', 0))
                
                self._send_message(
                    "media_data",
                    media_id=item.get('id'),
                    media_type="photo" if media_type == 1 else "video" if media_type == 2 else "carousel",
                    image_url=best_image.get('url'),
                    width=best_image.get('width'),
                    height=best_image.get('height'),
                    like_count=item.get('like_count', 0),
                    comment_count=item.get('comment_count', 0),
                    caption=item.get('caption', {}).get('text', '') if item.get('caption') else '',
                    taken_at=item.get('taken_at'),
                    username=item.get('user', {}).get('username')
                )
                
            # Handle carousel items
            if media_type == 8:
                carousel_media = item.get('carousel_media', [])
                for i, carousel_item in enumerate(carousel_media[:3]):  # Limit to 3
                    carousel_candidates = carousel_item.get('image_versions2', {}).get('candidates', [])
                    if carousel_candidates:
                        best = max(carousel_candidates, key=lambda x: x.get('width', 0))
                        self._send_message(
                            "carousel_media",
                            parent_media_id=item.get('id'),
                            index=i,
                            image_url=best.get('url'),
                            width=best.get('width'),
                            height=best.get('height')
                        )
                        
        except Exception as e:
            ctx.log.error(f"Media parse error: {e}")
    
    def _handle_cdn_response(self, flow: http.HTTPFlow):
        """Handle CDN image responses."""
        try:
            url = flow.request.pretty_url
            content_type = flow.response.headers.get('content-type', '')
            
            # Only process images
            if 'image' not in content_type:
                return
            
            content_length = len(flow.response.content)
            image_type = self._detect_image_type(url, content_length)
            url_hash = self._hash_url(url)
            
            # Deduplicate
            if url_hash in self.captured_media:
                return
            
            self.captured_media[url_hash] = True
            
            # Send capture notification
            self._send_message(
                "cdn_capture",
                url=url,
                image_type=image_type,
                size=content_length,
                content_type=content_type,
                username=self.current_profile,
                url_hash=url_hash
            )
            
        except Exception as e:
            ctx.log.error(f"CDN capture error: {e}")


# Register the addon
addons = [InstagramCDNCapture()]
