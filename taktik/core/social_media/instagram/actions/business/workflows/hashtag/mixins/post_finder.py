"""Post finding, grid navigation, and metadata extraction for hashtag workflow.

Internal structure:
- post_detection.py — Post type detection, reel handling, grid detection, swipe helpers
- post_finder.py    — Post finding logic, grid opening, metadata extraction (this file)
"""

import time
from typing import Dict, List, Any, Optional

from taktik.core.database.instagram_hashtag_posts import InstagramHashtagPostService
from taktik.core.social_media.instagram.ui.extractors import parse_number_from_text, username_from_media_label
from .post_detection import HashtagPostDetectionMixin


class HashtagPostFinderMixin(HashtagPostDetectionMixin):
    """Mixin: find valid posts in hashtag grids, open posts, extract metadata."""
    
    def _find_first_valid_post(self, hashtag: str, config: Dict[str, Any], skip_count: int = 0) -> Optional[Dict[str, Any]]:
        """
        Find the first post valid against the like criteria.
        
        Args:
            hashtag: the hashtag to walk
            config: configuration holding the like bounds
            skip_count: valid posts to skip, to reach the Nth valid one
        """
        min_likes = config.get('min_likes', 100)
        max_likes = config.get('max_likes', 50000)
        max_attempts = 20 + skip_count  # More attempts when posts have to be skipped
        
        try:
            self.logger.info(f"Searching for valid post from #{hashtag} (criteria: {min_likes}-{max_likes} likes, skip_count={skip_count})")
            
            post_open_result = self._open_first_post_in_grid()
            if not post_open_result:
                self.logger.error("Failed to open first post")
                return None
            
            is_reel = post_open_result.get('is_reel', False) if isinstance(post_open_result, dict) else False
            
            posts_tested = 0
            valid_posts_found = 0  # Compteur de posts valides trouvés
            
            while posts_tested < max_attempts:
                # Should the session keep running (duration, caps)?
                if hasattr(self, 'session_manager') and self.session_manager:
                    should_continue, stop_reason = self.session_manager.should_continue()
                    if not should_continue:
                        self.logger.warning(f"🛑 Session stopped: {stop_reason}")
                        return None
                
                metadata = self._extract_post_metadata()
                
                if metadata:
                    likes_count = metadata.get('likes_count', 0)
                    comments_count = metadata.get('comments_count', 0)
                    
                    if min_likes <= likes_count <= max_likes:
                        valid_posts_found += 1
                        
                        # Si on doit encore sauter des posts valides
                        if valid_posts_found <= skip_count:
                            self.logger.info(f"Valid post #{valid_posts_found} (skipping, need to skip {skip_count}): {likes_count} likes")
                            # Swipe on to the next one
                            posts_tested += 1
                            if posts_tested < max_attempts:
                                if not self._swipe_to_next_post(known_signature=self._signature_of(metadata)):
                                    self.logger.warning("Stopped searching: cannot reach the next post")
                                    return None
                                is_reel = self._is_reel_post()
                            continue
                        
                        self.logger.info(f"Valid post found (#{posts_tested + 1}): {likes_count} likes, {comments_count} comments")
                        return {
                            'index': posts_tested,
                            'likes_count': likes_count,
                            'comments_count': comments_count,
                            'is_reel': is_reel
                        }
                    else:
                        if likes_count < min_likes:
                            reason = f"too few likes ({likes_count} < {min_likes})"
                        elif likes_count > max_likes:
                            reason = f"too many likes ({likes_count} > {max_likes})"
                        else:
                            reason = "criteria not met"
                        
                        self.logger.info(f"Post #{posts_tested + 1}: {likes_count} likes FILTERED ({reason})")
                else:
                    self.logger.debug(f"Post #{posts_tested + 1}: unable to extract metadata")
                
                posts_tested += 1

                if posts_tested < max_attempts:
                    # Advance AND confirm we moved. Scrolling blind here meant re-reading the
                    # same post up to `max_attempts` times and calling it "no valid post found".
                    if not self._swipe_to_next_post(known_signature=self._signature_of(metadata)):
                        self.logger.warning(f"Stopped searching after {posts_tested} post(s): cannot reach the next post")
                        return None
                    is_reel = self._is_reel_post()

            self.logger.warning(f"No valid post found after {max_attempts} attempts")
            return None
            
        except Exception as e:
            self.logger.error(f"Error searching for valid post: {e}")
            return None
    
    def _open_first_post_in_grid(self):
        max_attempts = 5
        
        for attempt in range(max_attempts):
            try:
                self.logger.debug(f"Attempt {attempt + 1}/{max_attempts} to open a post")
                
                post_selectors = self.post_selectors.hashtag_post_selectors
                
                posts = None
                used_selector = None
                for selector in post_selectors:
                    posts = self.device.xpath(selector).all()
                    if posts:
                        used_selector = selector
                        self.logger.debug(f"{len(posts)} posts found with: {selector}")
                        break
                
                if not posts:
                    self.logger.warning("No posts found in grid with all selectors")
                    return False
                
                self.logger.debug(f"Clicking first post (selector: {used_selector})")
                posts[0].click()
                time.sleep(3)
                
                post_type = self._detect_opened_post_type()
                self.logger.info(f"Post type detected: {post_type}")
                
                if post_type == "reel_player":
                    self.logger.debug("Reel detected - swipe up to reveal likes")
                    if self._reveal_reel_comments_section():
                        self.logger.debug("Reel comments section revealed")
                        return {'success': True, 'is_reel': True}
                    else:
                        self.logger.debug("Unable to reveal reel comments")
                        
                elif post_type == "post_detail":
                    self.logger.debug(f"Post detail opened (attempt {attempt + 1})")
                    return {'success': True, 'is_reel': False}
                    
                else:
                    self.logger.debug(f"Unknown post type or opening failed")
                
                if attempt < max_attempts - 1:
                    self.logger.debug("Back to grid to try another post")
                    self.device.back()
                    time.sleep(1.5)
                    
                    self.logger.debug("Scrolling in grid")
                    # Humanized controlled scroll in the hashtag grid (was fixed-centre swipe).
                    self.device.human_scroll("down", distance_ratio=0.2)
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.debug(f"Error attempt {attempt + 1}: {e}")
                continue
        
        self.logger.error(f"Failed to open a post after {max_attempts} attempts")
        return False
    
    def _extract_post_metadata(self) -> Optional[Dict[str, Any]]:
        try:
            is_reel = self._is_reel_post()
            metadata = {
                'likes_count': self.ui_extractors.extract_likes_count_from_ui(is_reel=is_reel),
                'comments_count': self.ui_extractors.extract_comments_count_from_ui(is_reel=is_reel),
                'is_reel': is_reel
            }
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error extracting metadata: {e}")
            return None
    
    def _validate_hashtag_limits(self, post_metadata: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        return self._validate_resource_limits(
            available=post_metadata.get('likes_count', 0),
            requested=config.get('max_interactions', 30),
            resource_name="likes"
        )
    
    # ============================================
    # POST METADATA EXTRACTION
    # ============================================
    
    def _extract_current_post_metadata(self, is_reel: bool = False) -> Optional[Dict[str, Any]]:
        """
        Extract the metadata of the currently displayed post.
        Used to identify a post uniquely and avoid handling it twice.
        
        Args:
            is_reel: True on a reel, False on a regular post
            
        Returns:
            Dict with author, caption, caption_hash, likes_count, comments_count
            ou None si extraction échouée
        """
        try:
            metadata = {
                'author': None,
                'caption': None,
                'caption_hash': None,
                'likes_count': None,
                'comments_count': None,
                'post_date': None
            }
            
            # Detect a reel, which is more reliable than the parameter
            is_reel_detected = self._is_reel_post()
            self.logger.debug(f"Post type detection: is_reel_param={is_reel}, is_reel_detected={is_reel_detected}")
            is_reel = is_reel or is_reel_detected  # True when either says so
            
            # Extraire l'auteur
            if is_reel:
                author_selectors = self.post_selectors.reel_author_username_selectors
            else:
                author_selectors = self.post_selectors.post_author_username_selectors
            
            for selector in author_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        # Try several ways to read the text
                        text = element.get_text()
                        if not text:
                            # Fallback: essayer content-desc
                            info = element.info
                            text = info.get('contentDescription', '') or info.get('text', '')
                        if text:
                            # Clean the username
                            metadata['author'] = text.strip().lstrip('@').lower()
                            self.logger.debug(f"📝 Post author: @{metadata['author']}")
                            break
                except Exception as e:
                    self.logger.debug(f"Author selector {selector} failed: {e}")
                    continue
            
            # Fallback: the author lives in the media label.
            if not metadata['author'] and is_reel:
                self.logger.debug("Trying fallback: extracting author from the reel media label")
                try:
                    reel_element = self.device.xpath(self._hashtag_sel.reel_author_container[-1])
                    if reel_element.exists:
                        info = reel_element.info
                        content_desc = info.get('contentDescription') or info.get('content-desc') or info.get('contentDesc') or ''
                        self.logger.debug(f"clips_media_component content-desc: '{content_desc[:100] if content_desc else 'empty'}'")

                        # Read whatever the language: that label is translated, and knowing only
                        # its English form meant having NO author at all on a device in another
                        # language — hence no deduplication window, which
                        # s'appuie dessus.
                        username = username_from_media_label(content_desc)
                        if username:
                            metadata['author'] = username
                            self.logger.debug(f"📝 Post author (from media label): @{metadata['author']}")
                    else:
                        self.logger.debug("clips_media_component not found")
                except Exception as e:
                    self.logger.debug(f"Reel media label extraction failed: {e}")
            
            # Extract the caption, and the date on reels
            if is_reel:
                caption_selectors = self.post_selectors.reel_caption_selectors
                # Read the caption first
                for selector in caption_selectors:
                    try:
                        element = self.device.xpath(selector)
                        if element.exists:
                            caption = element.info.get('contentDescription', '') or element.get_text() or ''
                            if caption:
                                # Is the caption collapsed?
                                if '…' in caption or '...' in caption:
                                    self.logger.debug(f"📝 Caption rétractée détectée: {caption[:30]}... - clic pour ouvrir")
                                    try:
                                        element.click()
                                        time.sleep(0.8)  # Attendre l'animation
                                        # Try again to read the full caption
                                        element = self.device.xpath(selector)
                                        if element.exists:
                                            caption = element.info.get('contentDescription', '') or element.get_text() or ''
                                    except Exception:
                                        pass
                                
                                metadata['caption'] = caption.strip()
                                metadata['caption_hash'] = InstagramHashtagPostService.generate_caption_hash(caption)
                                self.logger.debug(f"📝 Post caption: {caption[:80]}...")
                                break
                    except Exception:
                        continue
                
                # Extract the post date, visible once the caption is expanded
                try:
                    date_selectors = getattr(self.post_selectors, 'reel_date_selectors', [])
                    for selector in date_selectors:
                        elements = self.device.xpath(selector)
                        if elements.exists:
                            for elem in elements.all() if hasattr(elements, 'all') else [elements]:
                                date_text = elem.info.get('contentDescription', '') or elem.info.get('text', '') or elem.get_text() or ''
                                # Check it is a date (it holds a month name)
                                months = ['January', 'February', 'March', 'April', 'May', 'June', 
                                         'July', 'August', 'September', 'October', 'November', 'December']
                                if date_text and any(m in date_text for m in months):
                                    metadata['post_date'] = date_text.strip()
                                    self.logger.debug(f"📅 Post date: {metadata['post_date']}")
                                    break
                            if metadata.get('post_date'):
                                break
                except Exception as e:
                    self.logger.debug(f"Date extraction failed: {e}")
            else:
                caption_selectors = self.post_selectors.post_caption_selectors
                for selector in caption_selectors:
                    try:
                        element = self.device.xpath(selector)
                        if element.exists:
                            caption = element.info.get('contentDescription', '') or element.get_text() or ''
                            if caption:
                                metadata['caption'] = caption.strip()
                                metadata['caption_hash'] = InstagramHashtagPostService.generate_caption_hash(caption)
                                self.logger.debug(f"📝 Post caption preview: {caption[:50]}...")
                                break
                    except Exception:
                        continue
            
            # Extract the like count
            for selector in self.post_selectors.post_likes_count_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        # On reels the number is embedded in a sentence
                        content_desc = element.info.get('contentDescription', '')
                        text = element.get_text() or content_desc
                        
                        if text:
                            likes = parse_number_from_text(text)
                            if likes:
                                metadata['likes_count'] = likes
                                self.logger.debug(f"📝 Post likes: {likes}")
                                break
                except Exception:
                    continue
            
            # Extract the comment count
            for selector in self.post_selectors.post_comments_count_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        content_desc = element.info.get('contentDescription', '')
                        text = element.get_text() or content_desc
                        
                        if text:
                            comments = parse_number_from_text(text)
                            if comments:
                                metadata['comments_count'] = comments
                                self.logger.debug(f"📝 Post comments: {comments}")
                                break
                except Exception:
                    continue
            
            # REEL fallback. The two loops above query POST selectors; on a reel they often
            # come back empty and the counters stay unset — which the panel then shows as
            # nothing at all, while the same run reads that counter without trouble two
            # lines further down through the shared extractor, which is reel-aware. So it
            # is asked again rather than giving up.
            # Unset stays possible and stays legitimate: unreadable is not zero.
            if metadata['likes_count'] is None or metadata['comments_count'] is None:
                try:
                    if metadata['likes_count'] is None:
                        metadata['likes_count'] = self.ui_extractors.extract_likes_count_from_ui(is_reel=is_reel)
                    if metadata['comments_count'] is None:
                        metadata['comments_count'] = self.ui_extractors.extract_comments_count_from_ui(is_reel=is_reel)
                except Exception as exc:
                    self.logger.debug(f"Shared counter fallback failed: {exc}")

            # Vérifier qu'on a au moins l'auteur
            if metadata['author']:
                date_info = f" | date: {metadata['post_date']}" if metadata.get('post_date') else ""
                self.logger.info(f"📋 Post metadata: @{metadata['author']} | {metadata.get('likes_count', '?')} likes | caption_hash: {metadata.get('caption_hash', 'N/A')}{date_info}")
                return metadata
            else:
                self.logger.warning("⚠️ Could not extract post author")
                return None
                
        except Exception as e:
            self.logger.error(f"Error extracting post metadata: {e}")
            return None
