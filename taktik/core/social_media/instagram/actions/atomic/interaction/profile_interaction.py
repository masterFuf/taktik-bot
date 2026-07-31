"""Profile interaction actions (follow, unfollow, message, follow state detection)."""

from typing import Optional, Dict, Any, List
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors.surfaces.profile import PROFILE_SELECTORS
from ......shared.text import normalize_ui_label


# Instagram renders a TYPOGRAPHIC apostrophe (U+2019) in "S'abonner"; our catalogues are typed
# with the ASCII one. A plain substring test therefore never matched, and the row was skipped in
# silence. Normalising both sides is the fix — never "just add the curly variant too", which only
# moves the trap to the next label someone types. The folding now lives in `shared/text.py` so
# every label comparison shares it: it was MISSING in the notifications row matcher, where
# "Bouton J'aime" consequently never matched what the device renders.
_normalize_label = normalize_ui_label


def classify_follow_state(text: str, selectors) -> Optional[str]:
    """Traduit le TEXTE d'un bouton d'action (header profil OU ligne de liste) en etat de relation,
    via les libelles de la couche locale (`follow_state_labels_*` de `selectors`).

    Returns: 'following' | 'requested' | 'follow_back' | 'follow' | None (aucun match).

    ORDRE PORTEUR : following > requested > follow_back > follow. "Following" contient "Follow" et
    "Suivre en retour" contient "Suivre" — tester 'follow' en premier renverrait 'follow' pour un
    bouton "Suivre en retour". Les libelles des differents etats ne se recouvrent pas entre eux,
    donc l'ordre reste correct meme si `L()` retombe sur l'union multi-langue (Lab / sans detection).
    Source de verite UNIQUE, partagee par la lecture header et la lecture ligne-de-liste.
    """
    t = _normalize_label(text)
    if not t:
        return None

    def _m(labels) -> bool:
        return any(_normalize_label(lbl) in t
                   for lbl in (labels or []) if lbl and lbl.strip())

    # AVANT tout le reste : "Ne plus suivre" contient "Suivre", "Unfollow" contient
    # "Follow". Un bouton de desabonnement se lisait donc comme un bouton de suivi. On le
    # rend 'following' — c'est ce qu'il signifie, et cet etat n'est jamais tape.
    if _m(getattr(selectors, 'follow_state_labels_unfollow', None)):
        return 'following'
    if _m(selectors.follow_state_labels_following):
        return 'following'
    if _m(selectors.follow_state_labels_requested):
        return 'requested'
    if _m(selectors.follow_state_labels_follow_back):
        return 'follow_back'
    if _m(selectors.follow_state_labels_follow):
        return 'follow'
    return None


class ProfileInteractionMixin(BaseAction):
    """Mixin: follow/unfollow, message button, follow state detection, review popup."""

    def click_follow_button(self) -> bool:
        return self._click_button(self.profile_selectors.follow_button, "Follow button", "👤")
    
    def click_unfollow_button(self) -> bool:
        return self._click_button(self.profile_selectors.following_button, "Unfollow button", "👤")

    def click_message_button(self) -> bool:
        return self._click_button(self.profile_selectors.message_button, "Message button", "💌")

    def click_followers_count(self) -> bool:
        return self._click_button(self.profile_selectors.followers_count, "Followers count", "👥")
    
    def click_following_count(self) -> bool:
        return self._click_button(self.profile_selectors.following_count, "Following count", "👥")
    
    def click_posts_count(self) -> bool:
        return self._click_button(self.profile_selectors.posts_count, "Posts count", "📸")

    def is_follow_button_available(self) -> bool:
        return self._is_element_present(self.profile_selectors.follow_button)
    
    def is_unfollow_button_available(self) -> bool:
        return self._is_element_present(self.profile_selectors.following_button)

    # === Follow workflow ===

    def follow_user(self, username: str) -> bool:
        try:
            self.logger.info(f"👤 Attempting to follow @{username}")
            
            # follow_button is a List[str] property — spread it (a bare entry would nest a list
            # inside follow_selectors and make device.xpath() raise "Invalid attr").
            follow_selectors = PROFILE_SELECTORS.advanced_follow_selectors + [
                *PROFILE_SELECTORS.follow_button,
                PROFILE_SELECTORS.follow_buttons,
                PROFILE_SELECTORS.suivre_buttons
            ]
            
            if self._find_and_click(follow_selectors, timeout=5):
                # Vérifier qu'on n'a pas navigué vers la liste des followers
                self._human_like_delay('click')
                
                # Check for "Review this account before following" popup
                if self._handle_review_account_popup():
                    self.logger.info(f"📋 Handled 'Review account' popup for @{username}")
                    self._human_like_delay('click')
                
                if self._verify_follow_success(username):
                    self.logger.info(f"✅ Successfully followed @{username}")
                    # Note: L'événement follow_event est émis par le workflow (followers.py)
                    # pour inclure les données du profil. Ne pas dupliquer ici.
                    return True
                else:
                    self.logger.warning(f"❌ Clicked but not on the right button for @{username}")
                    return False
            else:
                self.logger.warning(f"❌ Follow button not found for @{username}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to follow @{username}: {e}")
            return False
    
    def _handle_review_account_popup(self) -> bool:
        """
        Handle the "Review this account before following" popup that appears for new accounts.
        Clicks the Follow button in the popup to confirm the follow action.
        
        Returns:
            True if popup was detected and handled, False otherwise
        """
        try:
            # Check if the popup is present
            for indicator in self.popup_selectors.review_account_popup_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.info("📋 'Review this account before following' popup detected")
                    
                    # Click the Follow button in the popup
                    for follow_btn in self.popup_selectors.review_account_follow_button:
                        if self.device.xpath(follow_btn).exists:
                            self.device.xpath(follow_btn).click()
                            self.logger.info("✅ Clicked Follow button in review popup")
                            return True
                    
                    self.logger.warning("⚠️ Review popup detected but Follow button not found")
                    return False
            
            return False
        except Exception as e:
            self.logger.error(f"Error handling review account popup: {e}")
            return False
    
    def _verify_follow_success(self, username: str) -> bool:
        try:
            for indicator in self.detection_selectors.followers_list_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.warning(f"❌ Navigation to list detected for @{username}")
                    self.device.press("back")
                    return False
            
            # Vérifier qu'on est toujours sur un profil
            from ..detection import DetectionActions
            detection = DetectionActions(self.device)
            
            if detection.is_on_profile_screen():
                self.logger.debug(f"✅ Still on profile after follow @{username}")
                return True
            else:
                self.logger.warning(f"❌ Not on profile after follow attempt @{username}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error verifying follow @{username}: {e}")
            return True

    # === Follow button state ===

    def get_follow_button_state(self) -> str:
        """
        Etat de la relation, lu sur le bouton d'action du header profil.

        Returns: 'follow' | 'follow_back' | 'following' | 'requested' | 'message' | 'unknown'

        - 'follow'      : aucune relation -> cible neuve
        - 'follow_back' : IL NOUS SUIT (bouton "Suivre en retour" / "Follow back")
        - 'following'   : ON LE SUIT deja
        - 'requested'   : demande envoyee (compte prive)

        On ancre par resource-id (neutre langue) puis on compare le TEXTE aux libelles de la couche
        locale — jamais de libelle en dur ici. L'ancrage par id est indispensable : une forme texte
        nue attraperait `profile_header_follow_context_text` ("Suivi(e) par X, Y" = amis en commun).

        ORDRE DE TEST PORTEUR : following > requested > follow_back > follow. "Following" contient
        "Follow" et "Suivre en retour" contient "Suivre" — tester 'follow' en premier renverrait
        'follow' pour un bouton "Suivre en retour" (le bug qui faisait re-cibler nos propres
        abonnes). Reste correct meme si `L()` retombe sur l'union multi-langue : les libelles des
        differents etats ne se recouvrent pas entre eux.
        """
        selectors = self.profile_selectors
        for anchor in selectors.follow_button_anchors:
            try:
                btn = self.device.xpath(anchor)
                if not btn.exists:
                    continue
                state = classify_follow_state(btn.get_text() or '', selectors)
                if state:
                    return state
            except Exception:
                continue

        # === FALLBACK: check Message button (means we already follow) ===
        if self._is_element_present(self.profile_selectors.message_button):
            return 'message'

        return 'unknown'
