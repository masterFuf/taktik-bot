"""Post discovery, grid navigation, reel detection, metadata extraction for hashtag workflow."""

import time
from typing import Dict, List, Any, Optional

from ...common.database_helpers import DatabaseHelpers
from taktik.core.social_media.instagram.ui.extractors import parse_number_from_text


class HashtagPostFinderMixin:
    """Mixin: find valid posts in hashtag grids, detect post types, extract metadata."""
    
    def _find_first_valid_post(self, hashtag: str, config: Dict[str, Any], skip_count: int = 0) -> Optional[Dict[str, Any]]:
        """
        Trouve le premier post valide selon les critères de likes.
        
        Args:
            hashtag: Le hashtag à analyser
            config: Configuration avec min_likes, max_likes
            skip_count: Nombre de posts valides à sauter (pour trouver le N-ième post valide)
        """
        min_likes = config.get('min_likes', 100)
        max_likes = config.get('max_likes', 50000)
        max_attempts = 20 + skip_count  # Augmenter les tentatives si on doit sauter des posts
        
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
                # Vérifier si la session doit continuer (durée, limites, etc.)
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
                            # Swiper pour passer au suivant
                            posts_tested += 1
                            if posts_tested < max_attempts:
                                width, height = self.device.get_screen_size()
                                center_x = width // 2
                                start_y = int(height * 0.83)
                                end_y = int(height * 0.21)
                                self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.6)
                                time.sleep(3)
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
                    # Adaptive swipe coordinates
                    width, height = self.device.get_screen_size()
                    center_x = width // 2
                    start_y = int(height * 0.83)  # ~83% of height
                    end_y = int(height * 0.21)    # ~21% of height
                    self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.6)
                    time.sleep(3)
                    is_reel = self._is_reel_post()
            
            self.logger.warning(f"No valid post found after {max_attempts} attempts")
            return None
            
        except Exception as e:
            self.logger.error(f"Error searching for valid post: {e}")
            return None
    
    def _swipe_to_next_post(self):
        """Swipe vertical pour passer au post suivant."""
        try:
            width, height = self.device.get_screen_size()
            center_x = width // 2
            start_y = int(height * 0.75)
            end_y = int(height * 0.25)
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.4)
            self.logger.debug("📜 Swiped to next post")
        except Exception as e:
            self.logger.debug(f"Error swiping to next post: {e}")
    
    def _is_on_hashtag_grid(self) -> bool:
        """Vérifie si on est sur la grille de posts d'un hashtag."""
        try:
            # Vérifier si on voit des posts dans la grille
            for selector in self.post_selectors.hashtag_post_selectors:
                posts = self.device.xpath(selector).all()
                if posts and len(posts) >= 3:  # Au moins 3 posts visibles = grille
                    self.logger.debug(f"✅ Hashtag grid detected ({len(posts)} posts visible)")
                    return True
            
            # Vérifier si on voit le header du hashtag (depuis selectors.py)
            for selector in self._hashtag_sel.hashtag_header:
                if self.device.xpath(selector).exists:
                    self.logger.debug("✅ Hashtag page header detected")
                    return True
            
            self.logger.debug("❌ Not on hashtag grid")
            return False
        except Exception as e:
            self.logger.debug(f"Error checking hashtag grid: {e}")
            return False
    
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
                    screen_info = self.device.info
                    center_x = screen_info.get('displayWidth', 1080) // 2
                    start_y = int(screen_info.get('displayHeight', 1920) * 0.6)
                    end_y = int(screen_info.get('displayHeight', 1920) * 0.4)
                    self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.4)
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.debug(f"Error attempt {attempt + 1}: {e}")
                continue
        
        self.logger.error(f"Failed to open a post after {max_attempts} attempts")
        return False
    
    def _detect_opened_post_type(self) -> str:
        try:
            reel_player_indicators = self.post_selectors.reel_player_indicators
            
            for indicator in reel_player_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"Reel player detected via: {indicator}")
                    return "reel_player"
            
            carousel_indicators = self.post_selectors.carousel_indicators
            
            for indicator in carousel_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"Carousel detected via: {indicator}")
                    return "post_detail"
            
            post_detail_indicators = self.post_selectors.post_detail_indicators
            
            for indicator in post_detail_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"Post detail detected via: {indicator}")
                    return "post_detail"
            
            self.logger.warning("No post indicator found")
            return "unknown"
            
        except Exception as e:
            self.logger.debug(f"Error detecting post type: {e}")
            return "unknown"
    
    def _reveal_reel_comments_section(self) -> bool:
        try:
            screen_info = self.device.info
            center_x = screen_info.get('displayWidth', 1080) // 2
            
            start_y = int(screen_info.get('displayHeight', 1920) * 0.80)
            end_y = int(screen_info.get('displayHeight', 1920) * 0.20)
            
            self.logger.debug(f"Swipe to reveal comments: ({center_x}, {start_y}) -> ({center_x}, {end_y})")
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.5)
            time.sleep(2)
            
            if self._are_like_comment_elements_visible():
                self.logger.debug("Like/comment elements detected after 1st swipe")
                return True
            
            self.logger.debug("Second swipe to finalize opening")
            start_y = int(screen_info.get('displayHeight', 1920) * 0.70)
            end_y = int(screen_info.get('displayHeight', 1920) * 0.30)
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.5)
            time.sleep(2)
            
            result = self._are_like_comment_elements_visible()
            if result:
                self.logger.debug("Like/comment elements detected after 2nd swipe")
            else:
                self.logger.debug("Like/comment elements not detected")
            return result
            
        except Exception as e:
            self.logger.error(f"Error swiping to reveal comments: {e}")
            return False
    
    def _are_like_comment_elements_visible(self) -> bool:
        try:
            like_indicators = self.post_selectors.like_button_indicators
            comment_indicators = self.post_selectors.comment_button_indicators
            
            for selector in like_indicators + comment_indicators:
                try:
                    if self.device.xpath(selector).exists:
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Error checking elements: {e}")
            return False
    
    def _extract_post_metadata(self) -> Optional[Dict[str, Any]]:
        try:
            metadata = {
                'likes_count': self.ui_extractors.extract_likes_count_from_ui(),
                'comments_count': self.ui_extractors.extract_comments_count_from_ui(),
                'is_reel': self._is_reel_post()
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
        Extrait les métadonnées du post actuellement affiché.
        Utilisé pour identifier de manière unique un post et éviter de le retraiter.
        
        Args:
            is_reel: True si on est sur un Reel, False pour un post classique
            
        Returns:
            Dict avec author, caption, caption_hash, likes_count, comments_count
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
            
            # Détecter si c'est un Reel (plus fiable que le paramètre)
            is_reel_detected = self._is_reel_post()
            self.logger.debug(f"Post type detection: is_reel_param={is_reel}, is_reel_detected={is_reel_detected}")
            is_reel = is_reel or is_reel_detected  # Utiliser True si l'un des deux est True
            
            # Extraire l'auteur
            if is_reel:
                author_selectors = self.post_selectors.reel_author_username_selectors
            else:
                author_selectors = self.post_selectors.post_author_username_selectors
            
            for selector in author_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        # Essayer plusieurs méthodes pour récupérer le texte
                        text = element.get_text()
                        if not text:
                            # Fallback: essayer content-desc
                            info = element.info
                            text = info.get('contentDescription', '') or info.get('text', '')
                        if text:
                            # Nettoyer le username
                            metadata['author'] = text.strip().lstrip('@').lower()
                            self.logger.debug(f"📝 Post author: @{metadata['author']}")
                            break
                except Exception as e:
                    self.logger.debug(f"Author selector {selector} failed: {e}")
                    continue
            
            # Fallback: extraire depuis "Reel by username" dans content-desc
            if not metadata['author'] and is_reel:
                self.logger.debug("Trying fallback: extracting author from 'Reel by' content-desc")
                try:
                    # Chercher l'élément clips_media_component qui contient "Reel by username" (depuis selectors.py)
                    reel_element = self.device.xpath(self._hashtag_sel.reel_author_container[-1])
                    if reel_element.exists:
                        info = reel_element.info
                        # Essayer plusieurs clés possibles pour content-desc
                        content_desc = info.get('contentDescription') or info.get('content-desc') or info.get('contentDesc') or ''
                        self.logger.debug(f"clips_media_component info keys: {list(info.keys())}")
                        self.logger.debug(f"clips_media_component content-desc: '{content_desc[:100] if content_desc else 'empty'}'")
                        
                        # Format: "Reel by username. Double-tap to play or pause."
                        if 'Reel by ' in content_desc:
                            username = content_desc.split('Reel by ')[1].split('.')[0].strip()
                            if username:
                                metadata['author'] = username.lower()
                                self.logger.debug(f"📝 Post author (from Reel by): @{metadata['author']}")
                    else:
                        self.logger.debug("clips_media_component not found")
                except Exception as e:
                    self.logger.debug(f"Fallback Reel by extraction failed: {e}")
            
            # Extraire la caption (et la date pour les Reels)
            if is_reel:
                caption_selectors = self.post_selectors.reel_caption_selectors
                # Essayer d'abord de récupérer la caption
                for selector in caption_selectors:
                    try:
                        element = self.device.xpath(selector)
                        if element.exists:
                            caption = element.info.get('contentDescription', '') or element.get_text() or ''
                            if caption:
                                # Vérifier si la caption est rétractée (contient "…" ou "...")
                                if '…' in caption or '...' in caption:
                                    self.logger.debug(f"📝 Caption rétractée détectée: {caption[:30]}... - clic pour ouvrir")
                                    try:
                                        element.click()
                                        time.sleep(0.8)  # Attendre l'animation
                                        # Réessayer de récupérer la caption complète
                                        element = self.device.xpath(selector)
                                        if element.exists:
                                            caption = element.info.get('contentDescription', '') or element.get_text() or ''
                                    except Exception:
                                        pass
                                
                                metadata['caption'] = caption.strip()
                                metadata['caption_hash'] = DatabaseHelpers.generate_caption_hash(caption)
                                self.logger.debug(f"📝 Post caption: {caption[:80]}...")
                                break
                    except Exception:
                        continue
                
                # Extraire la date du post (visible après ouverture de la caption)
                try:
                    date_selectors = getattr(self.post_selectors, 'reel_date_selectors', [])
                    for selector in date_selectors:
                        elements = self.device.xpath(selector)
                        if elements.exists:
                            for elem in elements.all() if hasattr(elements, 'all') else [elements]:
                                date_text = elem.info.get('contentDescription', '') or elem.info.get('text', '') or elem.get_text() or ''
                                # Vérifier que c'est une date (contient un mois)
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
                                metadata['caption_hash'] = DatabaseHelpers.generate_caption_hash(caption)
                                self.logger.debug(f"📝 Post caption preview: {caption[:50]}...")
                                break
                    except Exception:
                        continue
            
            # Extraire le nombre de likes
            for selector in self.post_selectors.post_likes_count_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        # Pour les reels, le format est "The like number is X. View likes."
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
            
            # Extraire le nombre de commentaires
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
