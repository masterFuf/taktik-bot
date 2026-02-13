"""
Content Workflow - Gestion de la publication de contenu Instagram
Permet de poster des posts, stories et reels

Internal structure (SRP split):
- content_ui_helpers.py — UI interaction helpers (creation UI, gallery, popups, publishing)
- content_workflow.py   — Orchestrator (this file)
"""
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from loguru import logger

from ....ui.selectors import CONTENT_CREATION_SELECTORS
from .content_ui_helpers import ContentUIHelpersMixin


class ContentWorkflow(ContentUIHelpersMixin):
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
