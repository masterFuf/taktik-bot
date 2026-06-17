"""UI interaction helpers for the Content workflow: creation UI, gallery, popups, publishing."""

import re
import time
from pathlib import Path
from typing import List, Optional

from taktik.core.shared.input.taktik_keyboard import type_with_taktik_keyboard
from taktik.core.shared.device.media_store import push_media, trigger_media_scan, scan_wait_for


class ContentUIHelpersMixin:
    """Mixin: open creation UI, select type, push image, gallery, popups, next, caption, location, publish."""

    def _first_text_button(self, labels: List[str], timeout: float = 2):
        """Return the first visible uiautomator2 text selector from a catalog list."""
        fallback = None
        for label in labels:
            button = self.device(text=label)
            fallback = button
            if button.exists(timeout=timeout):
                return button
        return fallback

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
            post_button = self._first_text_button(self.content_selectors.post_type_texts, timeout=5)
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

    def _select_reel_type(self) -> bool:
        """Sélectionner le type REEL"""
        try:
            self.logger.debug("Selecting REEL type...")

            reel_button = self._first_text_button(self.content_selectors.reel_type_texts, timeout=3)

            if reel_button.exists(timeout=5):
                reel_button.click()
                time.sleep(2)
                self.logger.debug("✅ REEL type selected")
                self._handle_reel_draft_modal()
                return True

            self.logger.error("REEL button not found")
            return False

        except Exception as e:
            self.logger.error(f"Error selecting REEL type: {e}")
            return False

    def _handle_reel_draft_modal(self) -> bool:
        """Detect the reel draft modal and immediately reset it with 'Start new video'."""
        try:
            headline_detected = False

            for headline_text in self.content_selectors.reel_draft_headlines:
                draft_headline = self.device(
                    resourceId=self.content_selectors.draft_headline,
                    text=headline_text,
                )
                if draft_headline.exists(timeout=1.5):
                    headline_detected = True
                    break

            if not headline_detected:
                draft_headline = self.device(resourceId=self.content_selectors.draft_headline)
                headline_detected = draft_headline.exists(timeout=1.0)

            if not headline_detected:
                self.logger.debug("No reel draft modal detected")
                return False

            self.logger.debug("Detected reel draft modal")

            for button_text in self.content_selectors.reel_draft_start_new_texts:
                start_new_button = self.device(
                    resourceId=self.content_selectors.auxiliary_button,
                    text=button_text,
                )
                if start_new_button.exists(timeout=1.5):
                    self.logger.debug(f"Found draft reset button ({button_text})")
                    start_new_button.click()
                    time.sleep(1.2)
                    self.logger.debug("Draft modal dismissed with Start new video")
                    return True

            aux_button = self.device(resourceId=self.content_selectors.auxiliary_button)
            if aux_button.exists(timeout=1.5):
                self.logger.debug("Using auxiliary draft button fallback")
                aux_button.click()
                time.sleep(1.2)
                self.logger.debug("Draft modal dismissed via fallback")
                return True

            self.logger.warning("Reel draft modal detected but no reset button was found")
            return False

        except Exception as e:
            self.logger.warning(f"Error handling reel draft modal: {e}")
            return False

    def _select_story_type(self) -> bool:
        """Sélectionner le type STORY"""
        try:
            self.logger.debug("Selecting STORY type...")
            
            # Chercher le bouton "STORY" en bas de l'écran
            story_button = self._first_text_button(self.content_selectors.story_type_texts, timeout=5)
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
        """Push an image/video to the device using the shared media_store service.

        Uses Android-version-aware MediaStore indexing (broadcast on SDK<29,
        content insert with integer timestamps on SDK>=29) so the file appears
        at the top of the gallery picker.
        """
        try:
            device_id = getattr(self.device_manager, 'device_id', None)
            if not device_id:
                self.logger.error("No device_id available — cannot push image")
                return None

            self.logger.debug(f"Pushing image to device: {local_path}")
            remote_path = push_media(device_id, local_path)
            if not remote_path:
                self.logger.error("push_media failed")
                return None

            trigger_media_scan(device_id, remote_path, local_path)
            time.sleep(scan_wait_for(local_path))
            self.logger.debug(f"✅ Image pushed to: {remote_path}")
            return remote_path

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
            
            first_image = self.device(
                **self.content_selectors.gallery_image_container_selector
            ).child(resourceId=self.content_selectors.gallery_grid_item)
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
            
            for button_text in self.content_selectors.popup_button_texts:
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
            if self._handle_reel_draft_modal():
                self.logger.debug("Draft modal intercepted before clicking Next")
            time.sleep(1.5)
            
            next_button = self.device(resourceId=self.content_selectors.next_button)
            if next_button.exists(timeout=5):
                self.logger.debug("Found Next button (method 1: resourceId)")
                next_button.click()
                time.sleep(1.5)
                self.logger.debug("✅ Next clicked")
                return True

            next_button = self.device(resourceId=self.content_selectors.share_button)
            if next_button.exists(timeout=3):
                self.logger.debug("Found Next button (method 1b: share_button)")
                next_button.click()
                time.sleep(1.5)
                self.logger.debug("✅ Next clicked")
                return True

            next_button = self.device(resourceId=self.content_selectors.clips_right_action_button)
            if next_button.exists(timeout=3):
                self.logger.debug("Found Next button (method 1c: clips_right_action_button)")
                next_button.click()
                time.sleep(1.5)
                self.logger.debug("✅ Next clicked")
                return True
            
            for label in self.content_selectors.next_texts:
                next_button = self.device(text=label)
                if next_button.exists(timeout=2):
                    self.logger.debug(f"Found Next button (text: {label})")
                    next_button.click()
                    time.sleep(1.5)
                    self.logger.debug("✅ Next clicked")
                    return True

            for description in self.content_selectors.next_descriptions:
                next_button = self.device(description=description)
                if next_button.exists(timeout=2):
                    self.logger.debug(f"Found Next button (content-desc: {description})")
                    next_button.click()
                    time.sleep(1.5)
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
                self.logger.debug(f"Adding caption ({len(caption)} chars)...")
            
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
                caption_field = self._first_text_button(self.content_selectors.caption_placeholder_texts, timeout=5)
            
            if caption_field.exists(timeout=5):
                caption_field.click()
                time.sleep(0.5)
                # Use Taktik Keyboard for reliable text input
                device_id = getattr(self.device_manager, 'device_id', None) or 'emulator-5554'
                if not type_with_taktik_keyboard(device_id, full_text):
                    self.logger.warning("Taktik Keyboard failed, falling back to set_text")
                    caption_field.set_text(full_text)
                time.sleep(0.8)
                self._dismiss_caption_keyboard()
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
            
            location_button = self._first_text_button(self.content_selectors.location_button_texts, timeout=3)
            if location_button.exists(timeout=3):
                location_button.click()
                time.sleep(1)
                
                # Rechercher la localisation
                search_field = self.device(**self.content_selectors.location_search_field_selector)
                if search_field.exists(timeout=3):
                    # Use Taktik Keyboard for reliable text input
                    device_id = getattr(self.device_manager, 'device_id', None) or 'emulator-5554'
                    if not type_with_taktik_keyboard(device_id, location):
                        self.logger.warning("Taktik Keyboard failed, falling back to set_text")
                        search_field.set_text(location)
                    time.sleep(2)
                    
                    # Sélectionner le premier résultat
                    first_result = self.device(**self.content_selectors.location_first_result_selector)
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

            # Instagram reels can bounce between:
            # 1) caption/share screen → share_button (content-desc often still "Next")
            # 2) edit video screen → clips_right_action_button ("Next")
            # 3) final share/publish screen → text button Share/Partager
            for attempt in range(4):
                if self._handle_reel_draft_modal():
                    self.logger.debug("Draft modal intercepted during publish flow")
                    continue

                if self._is_instagram_edit_video_screen():
                    self.logger.debug("Detected Instagram edit video screen, clicking Next")
                    if self._click_next():
                        continue

                if self._tap_caption_share_button():
                    self.logger.debug("Tapped caption/share button")
                    time.sleep(1.2)
                    continue

                share_button = self._first_text_button(self.content_selectors.publish_texts, timeout=2)

                if share_button.exists(timeout=3):
                    share_button.click()
                    time.sleep(2)
                    self.logger.debug("✅ Post published")
                    return True

                if attempt < 3 and self._click_next():
                    continue

            self.logger.error("Share button not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error publishing post: {e}")
            return False

    def _dismiss_caption_keyboard(self) -> None:
        """Close the Android keyboard if it is still covering the bottom action area."""
        try:
            if not self.device(**self.content_selectors.keyboard_window_selector).exists(timeout=1):
                return
        except Exception:
            pass

        try:
            self.device.press("back")
            time.sleep(0.4)
        except Exception as e:
            self.logger.debug(f"Keyboard dismiss failed: {e}")

    def _tap_caption_share_button(self) -> bool:
        """Tap the bottom-right action on Instagram's caption/share screen."""
        try:
            button = self.device(resourceId=self.content_selectors.share_button)
            if button.exists(timeout=2):
                button.click()
                return True

            for description in self.content_selectors.next_descriptions:
                button = self.device(description=description)
                if button.exists(timeout=2):
                    button.click()
                    return True
        except Exception as e:
            self.logger.debug(f"Caption share button tap failed: {e}")
        return False

    def _is_instagram_edit_video_screen(self) -> bool:
        """Detect Instagram's reel edit-video screen from the current dump."""
        try:
            xml = self.device.dump_hierarchy(compressed=False).lower()
            return (
                any(indicator.lower() in xml for indicator in self.content_selectors.edit_video_indicators)
                or self.content_selectors.clips_right_action_button in xml
                or re.search(self.content_selectors.edit_video_next_to_clips_pattern, xml, re.DOTALL) is not None
            )
        except Exception:
            return False

    def _publish_story(self) -> bool:
        """Publier la story"""
        try:
            self.logger.debug("Publishing story...")
            
            share_button = self._first_text_button(self.content_selectors.story_publish_texts, timeout=3)
            
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
