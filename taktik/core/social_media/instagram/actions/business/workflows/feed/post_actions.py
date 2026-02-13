"""Feed post actions: like, comment, detect, scroll, extract metadata."""

import time
import random
from typing import Dict, List, Any, Optional


class FeedPostActionsMixin:
    """Mixin: post-level actions in the feed (like, comment, detect, scroll)."""

    def _is_sponsored_post(self) -> bool:
        """Vérifier si le post actuel est sponsorisé."""
        return self._is_element_present(self._feed_selectors['sponsored_indicators'])
    
    def _is_reel_post(self) -> bool:
        """Vérifier si le post actuel est un Reel."""
        try:
            reel_indicators = self._feed_sel.reel_indicators
            
            for selector in reel_indicators:
                element = self.device.xpath(selector)
                if element.exists:
                    return True
            
            return False
        except Exception as e:
            self.logger.debug(f"Error checking if reel: {e}")
            return False
    
    def _get_current_post_author(self) -> Optional[str]:
        """Récupérer le username de l'auteur du post actuel."""
        try:
            for selector in self._feed_selectors['post_author_username']:
                element = self.device.xpath(selector)
                if element.exists:
                    username = element.get_text()
                    if username:
                        return self._clean_username(username)
            
            # Fallback: essayer via content-desc de l'avatar
            for selector in self._feed_selectors['post_author_avatar']:
                element = self.device.xpath(selector)
                if element.exists:
                    content_desc = element.attrib.get('content-desc', '')
                    if content_desc:
                        # Le content-desc contient souvent "Photo de profil de username"
                        parts = content_desc.split()
                        for part in parts:
                            if self._is_valid_username(part):
                                return self._clean_username(part)
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error getting post author: {e}")
            return None
    
    def _like_current_post(self) -> bool:
        """Liker le post actuellement visible dans le feed."""
        try:
            like_button_selectors = self._feed_sel.like_button
            
            # D'abord vérifier si le post est déjà liké
            for selector in like_button_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    content_desc = element.attrib.get('content-desc', '').lower()
                    # Vérifier si déjà liké (unlike = déjà liké)
                    if 'unlike' in content_desc or 'ne plus aimer' in content_desc or 'liked' in content_desc:
                        self.logger.debug("⏭️ Post already liked, skipping")
                        return False
                    
                    # Cliquer sur le bouton like
                    element.click()
                    self._human_like_delay('click')
                    return True
            
            # Fallback: vérifier via l'icône du coeur si le post est déjà liké
            # avant de faire un double tap
            already_liked_selectors = self._feed_sel.already_liked_indicators
            
            for selector in already_liked_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    self.logger.debug("⏭️ Post already liked (detected via unlike button), skipping")
                    return False
            
            # Double tap seulement si on n'a pas trouvé de bouton like ET le post n'est pas déjà liké
            self.logger.debug("Like button not found, trying double tap")
            screen_height = self.device.info.get('displayHeight', 1920)
            screen_width = self.device.info.get('displayWidth', 1080)
            center_x = screen_width // 2
            center_y = int(screen_height * 0.4)  # Milieu du post
            
            self.device.double_click(center_x, center_y)
            self._human_like_delay('click')
            return True
            
        except Exception as e:
            self.logger.debug(f"Error liking post: {e}")
            return False
    
    def _extract_post_metadata(self) -> Optional[Dict[str, Any]]:
        """Extraire les métadonnées du post actuellement visible (likes, commentaires)."""
        try:
            metadata = {
                'likes_count': self.ui_extractors.extract_likes_count_from_ui(),
                'comments_count': self.ui_extractors.extract_comments_count_from_ui(),
                'is_reel': self._is_reel_post()
            }
            
            self.logger.debug(f"📊 Post metadata: {metadata['likes_count']} likes, {metadata['comments_count']} comments")
            return metadata
            
        except Exception as e:
            self.logger.debug(f"Error extracting post metadata: {e}")
            return None
    
    def _comment_current_post(self, config: Dict[str, Any]) -> bool:
        """Commenter le post actuellement visible dans le feed."""
        try:
            # Récupérer les commentaires personnalisés ou utiliser des commentaires par défaut
            custom_comments = config.get('custom_comments', [])
            if not custom_comments:
                custom_comments = ['👏', '🔥', '💯', '❤️', '👍', '😍', '✨', '🙌']
            
            comment_text = random.choice(custom_comments)
            
            comment_button_selectors = self._feed_sel.comment_button
            
            # Cliquer sur le bouton commentaire
            for selector in comment_button_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    self._human_like_delay('click')
                    break
            else:
                self.logger.debug("Comment button not found")
                return False
            
            time.sleep(1)
            
            comment_input_selectors = self._feed_sel.comment_input
            
            for selector in comment_input_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    time.sleep(0.5)
                    # Use Taktik Keyboard for reliable text input
                    if not self._type_with_taktik_keyboard(comment_text):
                        self.logger.warning("Taktik Keyboard failed, falling back to set_text")
                        element.set_text(comment_text)
                    self._human_like_delay('typing')
                    break
            else:
                self.logger.debug("Comment input not found")
                self.device.press('back')
                return False
            
            send_button_selectors = self._feed_sel.comment_send_button
            
            for selector in send_button_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    self._human_like_delay('click')
                    time.sleep(1)
                    # Retourner au feed
                    self.device.press('back')
                    return True
            
            self.logger.debug("Send button not found")
            self.device.press('back')
            return False
            
        except Exception as e:
            self.logger.debug(f"Error commenting post: {e}")
            try:
                self.device.press('back')
            except:
                pass
            return False
    
    def _scroll_to_next_post(self):
        """Scroller vers le post suivant dans le feed."""
        try:
            # Scroll d'environ 70% de l'écran pour passer au post suivant
            screen_height = self.device.info.get('displayHeight', 1920)
            screen_width = self.device.info.get('displayWidth', 1080)
            
            start_y = int(screen_height * 0.7)
            end_y = int(screen_height * 0.2)
            center_x = screen_width // 2
            
            self.device.swipe(center_x, start_y, center_x, end_y, duration=0.3)
            
        except Exception as e:
            self.logger.debug(f"Error scrolling to next post: {e}")
            # Fallback: utiliser scroll_actions
            self.scroll_actions.scroll_down()
