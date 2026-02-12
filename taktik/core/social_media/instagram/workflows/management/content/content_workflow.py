"""
Content Workflow - Gestion de la publication de contenu Instagram
Permet de poster des posts, stories et reels
"""
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from loguru import logger

from ....ui.selectors import CONTENT_CREATION_SELECTORS
from ....utils.taktik_keyboard import type_with_taktik_keyboard


class ContentWorkflow:
    """Workflow pour publier du contenu sur Instagram"""
    
    def __init__(self, device_manager, nav_actions, detection_actions):
        """
        Initialize content workflow.
        
        Args:
            device_manager: Device manager instance
            nav_actions: Navigation actions instance
            detection_actions: Detection actions instance
        """
        self.device_manager = device_manager
        self.nav_actions = nav_actions
        self.detection_actions = detection_actions
        self.device = device_manager.device
        self.logger = logger
        self.content_selectors = CONTENT_CREATION_SELECTORS
    
    def post_single_photo(
        self,
        image_path: str,
        caption: Optional[str] = None,
        location: Optional[str] = None,
        hashtags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Poster une photo unique sur Instagram."""
        result = {
            'success': False,
            'message': '',
            'image_path': image_path
        }
        
        try:
            # Vérifier que le fichier existe
            if not Path(image_path).exists():
                result['message'] = f"Image not found: {image_path}"
                self.logger.error(result['message'])
                return result
            
            self.logger.info(f"📸 Starting post creation with image: {image_path}")
            
            if not self._open_content_creation():
                result['message'] = "Failed to open content creation"
                return result
            
            if not self._select_post_type():
                result['message'] = "Failed to select POST type"
                return result
            
            device_image_path = self._push_image_to_device(image_path)
            if not device_image_path:
                result['message'] = "Failed to push image to device"
                return result
            
            if not self._select_image_from_gallery(device_image_path):
                result['message'] = "Failed to select image from gallery"
                return result
            
            if not self._click_next():
                result['message'] = "Failed to click Next (first)"
                return result
            
            self._handle_popups()
            
            if not self._click_next():
                result['message'] = "Failed to click Next (second)"
                return result
            
            self._handle_popups()
            
            if caption or hashtags:
                if not self._add_caption(caption, hashtags):
                    result['message'] = "Failed to add caption"
                    return result
            
            if location:
                if not self._add_location(location):
                    self.logger.warning(f"Failed to add location: {location}")
            
            if not self._publish_post():
                result['message'] = "Failed to publish post"
                return result
            
            result['success'] = True
            result['message'] = "Post published successfully"
            self.logger.success(f"✅ Post published: {image_path}")
            
        except Exception as e:
            result['message'] = f"Error: {str(e)}"
            self.logger.error(f"Error posting image: {e}")
        
        return result
    
    def post_story(
        self,
        image_path: str,
        duration: int = 5
    ) -> Dict[str, Any]:
        """
        Poster une story sur Instagram.
        
        Args:
            image_path: Chemin vers l'image de la story
            duration: Durée d'affichage (pour validation)
            
        Returns:
            Dict avec le statut de la publication
        """
        result = {
            'success': False,
            'message': '',
            'image_path': image_path
        }
        
        try:
            if not Path(image_path).exists():
                result['message'] = f"Image not found: {image_path}"
                self.logger.error(result['message'])
                return result
            
            self.logger.info(f"📱 Starting story creation with image: {image_path}")
            
            # 1. Ouvrir la création de contenu
            if not self._open_content_creation():
                result['message'] = "Failed to open content creation"
                return result
            
            # 2. Sélectionner le type "STORY"
            if not self._select_story_type():
                result['message'] = "Failed to select STORY type"
                return result
            
            # 3. Pousser l'image sur le device
            device_image_path = self._push_image_to_device(image_path)
            if not device_image_path:
                result['message'] = "Failed to push image to device"
                return result
            
            # 4. Sélectionner l'image depuis la galerie
            if not self._select_image_from_gallery(device_image_path):
                result['message'] = "Failed to select image from gallery"
                return result
            
            # 5. Publier la story
            if not self._publish_story():
                result['message'] = "Failed to publish story"
                return result
            
            result['success'] = True
            result['message'] = "Story published successfully"
            self.logger.success(f"✅ Story published: {image_path}")
            
        except Exception as e:
            result['message'] = f"Error: {str(e)}"
            self.logger.error(f"Error posting story: {e}")
        
        return result
    
    def post_multiple_photos(
        self,
        image_paths: List[str],
        captions: Optional[List[str]] = None,
        delay_between_posts: int = 60
    ) -> Dict[str, Any]:
        """
        Poster plusieurs photos successivement.
        
        Args:
            image_paths: Liste des chemins d'images
            captions: Liste des légendes (optionnel)
            delay_between_posts: Délai entre chaque post en secondes
            
        Returns:
            Dict avec les résultats de chaque publication
        """
        results = {
            'total': len(image_paths),
            'success': 0,
            'failed': 0,
            'posts': []
        }
        
        self.logger.info(f"📸 Starting bulk post: {len(image_paths)} images")
        
        for i, image_path in enumerate(image_paths):
            caption = captions[i] if captions and i < len(captions) else None
            
            self.logger.info(f"[{i+1}/{len(image_paths)}] Posting: {image_path}")
            
            post_result = self.post_single_photo(image_path, caption)
            results['posts'].append(post_result)
            
            if post_result['success']:
                results['success'] += 1
            else:
                results['failed'] += 1
            
            # Délai entre les posts (sauf pour le dernier)
            if i < len(image_paths) - 1:
                self.logger.info(f"⏳ Waiting {delay_between_posts}s before next post...")
                time.sleep(delay_between_posts)
        
        self.logger.success(f"✅ Bulk post completed: {results['success']}/{results['total']} successful")
        return results
    
    # ==================== MÉTHODES PRIVÉES ====================
    
    def _open_content_creation(self) -> bool:
        """Ouvrir l'interface de création de contenu"""
        try:
            self.logger.debug("Opening content creation interface...")
            
            # Cliquer sur le bouton "+" dans la tab bar
            creation_tab = self.device(resourceId=self.content_selectors.creation_tab)
            if creation_tab.exists(timeout=5):
                creation_tab.click()
                time.sleep(2)
                self.logger.debug("✅ Content creation opened")
                return True
            
            self.logger.error("❌ Creation tab not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error opening content creation: {e}")
            return False
    
    def _select_post_type(self) -> bool:
        """Sélectionner le type POST"""
        try:
            self.logger.debug("Selecting POST type...")
            
            # Chercher le bouton "POST" en bas de l'écran
            post_button = self.device(text="POST")
            if post_button.exists(timeout=5):
                post_button.click()
                time.sleep(1)
                self.logger.debug("✅ POST type selected")
                return True
            
            self.logger.warning("POST button not found, might already be selected")
            return True
            
        except Exception as e:
            self.logger.error(f"Error selecting POST type: {e}")
            return False
    
    def _select_story_type(self) -> bool:
        """Sélectionner le type STORY"""
        try:
            self.logger.debug("Selecting STORY type...")
            
            # Chercher le bouton "STORY" en bas de l'écran
            story_button = self.device(text="STORY")
            if story_button.exists(timeout=5):
                story_button.click()
                time.sleep(1)
                self.logger.debug("✅ STORY type selected")
                return True
            
            self.logger.error("STORY button not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error selecting STORY type: {e}")
            return False
    
    def _push_image_to_device(self, local_path: str) -> Optional[str]:
        """Pousser une image sur le device Android."""
        try:
            self.logger.debug(f"Pushing image to device: {local_path}")
            
            filename = Path(local_path).name
            self.device.shell("mkdir -p /sdcard/DCIM/Camera")
            time.sleep(0.5)
            
            device_path = f"/sdcard/DCIM/Camera/{filename}"
            self.device.push(local_path, device_path)
            time.sleep(1)
            
            self.logger.debug("Refreshing MediaStore to detect new image...")
            try:
                self.device.shell(f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://{device_path}")
                time.sleep(1)
                self.logger.debug("✅ MediaStore refreshed successfully")
            except Exception as e:
                self.logger.warning(f"Could not refresh MediaStore: {e}")
            
            self.logger.debug(f"✅ Image pushed to: {device_path}")
            return device_path
            
        except Exception as e:
            self.logger.error(f"Error pushing image: {e}")
            return None
    
    def _select_image_from_gallery(self, device_image_path: str) -> bool:
        """Sélectionner une image depuis la galerie"""
        try:
            self.logger.debug("Selecting image from gallery...")
            time.sleep(3)
            
            gallery_image = self.device(resourceId=self.content_selectors.gallery_grid_item)
            if gallery_image.exists(timeout=5):
                self.logger.debug("Found image (method 1: gallery_grid_item)")
                gallery_image.click()
                time.sleep(2)
                self.logger.debug("✅ Image selected from gallery")
                return True
            
            first_image = self.device(className="android.view.ViewGroup", clickable=True).child(resourceId=self.content_selectors.gallery_grid_item)
            if first_image.exists(timeout=5):
                self.logger.debug("Found image (method 2: ViewGroup child)")
                first_image.click()
                time.sleep(2)
                self.logger.debug("✅ Image selected from gallery")
                return True
            
            self.logger.error("Failed to find image in gallery")
            return False
            
        except Exception as e:
            self.logger.error(f"Error selecting image: {e}")
            return False
    
    def _handle_popups(self) -> bool:
        """Gérer les popups qui peuvent apparaître."""
        try:
            self.logger.debug("Checking for popups...")
            time.sleep(2)
            
            ok_button = self.device(resourceId=self.content_selectors.primary_button)
            if ok_button.exists(timeout=3):
                self.logger.debug("Found popup button (method 1: primary_button)")
                ok_button.click()
                time.sleep(2)
                self.logger.debug("✅ Popup closed")
                return True
            
            ok_button = self.device(resourceId=self.content_selectors.bb_primary_action)
            if ok_button.exists(timeout=3):
                self.logger.debug("Found popup button (method 2: bb_primary_action)")
                ok_button.click()
                time.sleep(2)
                self.logger.debug("✅ Popup closed")
                return True
            
            for button_text in ["OK", "Got it", "Continue", "Not now", "Skip"]:
                button = self.device(text=button_text)
                if button.exists(timeout=2):
                    self.logger.debug(f"Found popup button (text: {button_text})")
                    button.click()
                    time.sleep(2)
                    self.logger.debug(f"✅ Clicked {button_text}")
                    return True
            
            self.logger.debug("No popup found")
            return False
            
        except Exception as e:
            self.logger.warning(f"Error handling popups: {e}")
            return False
    
    def _click_next(self) -> bool:
        """Cliquer sur le bouton Next."""
        try:
            self.logger.debug("Clicking Next button...")
            time.sleep(3)
            
            next_button = self.device(resourceId=self.content_selectors.next_button)
            if next_button.exists(timeout=5):
                self.logger.debug("Found Next button (method 1: resourceId)")
                next_button.click()
                time.sleep(3)
                self.logger.debug("✅ Next clicked")
                return True
            
            next_button = self.device(text="Next")
            if next_button.exists(timeout=3):
                self.logger.debug("Found Next button (method 2: text)")
                next_button.click()
                time.sleep(3)
                self.logger.debug("✅ Next clicked")
                return True
            
            next_button = self.device(text="Suivant")
            if next_button.exists(timeout=3):
                self.logger.debug("Found Next button (method 3: text Suivant)")
                next_button.click()
                time.sleep(3)
                self.logger.debug("✅ Next clicked")
                return True
            
            self.logger.error("Next button not found with any method")
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking Next: {e}")
            return False
    
    def _add_caption(self, caption: Optional[str] = None, hashtags: Optional[List[str]] = None) -> bool:
        """Ajouter une légende et des hashtags au post"""
        try:
            full_text = ""
            
            if caption:
                full_text = caption
                self.logger.debug(f"Adding caption: {caption[:50]}...")
            
            if hashtags:
                hashtag_text = " ".join([f"#{tag.lstrip('#')}" for tag in hashtags])
                if full_text:
                    full_text = f"{full_text}\n\n{hashtag_text}"
                else:
                    full_text = hashtag_text
                self.logger.debug(f"Adding {len(hashtags)} hashtags")
            
            if not full_text:
                return True
            
            caption_field = self.device(resourceId=self.content_selectors.caption_text_view)
            if not caption_field.exists(timeout=5):
                caption_field = self.device(resourceId=self.content_selectors.caption_input_text_view)
            if not caption_field.exists(timeout=5):
                caption_field = self.device(text="Write a caption...")
            
            if caption_field.exists(timeout=5):
                caption_field.click()
                time.sleep(0.5)
                # Use Taktik Keyboard for reliable text input
                device_id = getattr(self.device_manager, 'device_id', None) or 'emulator-5554'
                if not type_with_taktik_keyboard(device_id, full_text):
                    self.logger.warning("Taktik Keyboard failed, falling back to set_text")
                    caption_field.set_text(full_text)
                time.sleep(0.5)
                self.logger.debug("✅ Caption and hashtags added")
                return True
            
            self.logger.warning("Caption field not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error adding caption: {e}")
            return False
    
    def _add_location(self, location: str) -> bool:
        """Ajouter une localisation au post"""
        try:
            self.logger.debug(f"Adding location: {location}")
            
            # Chercher le bouton "Add location"
            location_button = self.device(text="Add location")
            if location_button.exists(timeout=3):
                location_button.click()
                time.sleep(1)
                
                # Rechercher la localisation
                search_field = self.device(className="android.widget.EditText")
                if search_field.exists(timeout=3):
                    # Use Taktik Keyboard for reliable text input
                    device_id = getattr(self.device_manager, 'device_id', None) or 'emulator-5554'
                    if not type_with_taktik_keyboard(device_id, location):
                        self.logger.warning("Taktik Keyboard failed, falling back to set_text")
                        search_field.set_text(location)
                    time.sleep(2)
                    
                    # Sélectionner le premier résultat
                    first_result = self.device(className="android.widget.TextView", instance=0)
                    if first_result.exists(timeout=3):
                        first_result.click()
                        time.sleep(1)
                        self.logger.debug("✅ Location added")
                        return True
            
            self.logger.warning("Location feature not accessible")
            return False
            
        except Exception as e:
            self.logger.error(f"Error adding location: {e}")
            return False
    
    def _publish_post(self) -> bool:
        """Publier le post"""
        try:
            self.logger.debug("Publishing post...")
            
            # Chercher le bouton "Share" ou "Partager"
            share_button = self.device(text="Share")
            if not share_button.exists(timeout=3):
                share_button = self.device(text="Partager")
            
            if share_button.exists(timeout=5):
                share_button.click()
                time.sleep(3)
                self.logger.debug("✅ Post published")
                return True
            
            self.logger.error("Share button not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error publishing post: {e}")
            return False
    
    def _publish_story(self) -> bool:
        """Publier la story"""
        try:
            self.logger.debug("Publishing story...")
            
            # Pour une story, chercher "Your story" ou "Share"
            share_button = self.device(text="Share")
            if not share_button.exists(timeout=3):
                share_button = self.device(text="Your story")
            
            if share_button.exists(timeout=5):
                share_button.click()
                time.sleep(3)
                self.logger.debug("✅ Story published")
                return True
            
            self.logger.error("Story share button not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error publishing story: {e}")
            return False
