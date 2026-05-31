"""Credential input — fill username/password fields and click login button."""

import time

class CredentialsMixin:
    """Mixin: saisie username/password + clic bouton de connexion."""

    def _dismiss_autofill_dropdown(self) -> None:
        """
        Détecte et ferme le dropdown inline autofill via le catalogue auth
        qui pop sur les champs de saisie Instagram.
        Utilise BACK pour le fermer sans sélectionner de suggestion.
        """
        try:
            if self.device.xpath(self.auth_selectors.autofill_dataset_picker).exists:
                self.logger.debug("📋 Autofill dataset dropdown detected — dismissing with BACK")
                self.device.press("back")
                time.sleep(0.4)
        except Exception as e:
            self.logger.debug(f"Autofill dropdown check failed: {e}")

    def _clear_and_fill_field(self, element, text: str, field_name: str) -> bool:
        """
        Remplit un champ de saisie de manière robuste.

        Stratégie (du plus fiable au moins) :
        1. set_text(target) direct via accessibility — fonctionne même sur enabled=false
        2. Tap aux coordonnées du champ (bypass enabled=false) → clear → type ADB
        3. ctrl+a / delete → type ADB
        """
        # ── 1. Direct set_text ────────────────────────────────────────────
        # ACTION_SET_TEXT de l'accessibility service ignore souvent enabled=false.
        try:
            element.set_text(text)
            time.sleep(0.5)
            self._dismiss_autofill_dropdown()
            actual = ""
            try:
                actual = element.get_text() or ""
            except Exception:
                pass
            # Pour les champs password, get_text() retourne des bullets/étoiles ("••••")
            # ou "" selon la version Android/uiautomator2 — on ne peut pas s'y fier.
            # Si set_text n'a pas levé d'exception, on lui fait confiance directement.
            is_password_field = (field_name.lower() == "password")
            if is_password_field:
                self.logger.success(f"✅ {field_name} filled via set_text (password field, skipping text verification)")
                return True
            if actual.strip() == text.strip() or text.strip() in actual:
                self.logger.success(f"✅ {field_name} filled via set_text")
                return True
            self.logger.debug(f"set_text check: got '{actual[:30]}' (expected '{text[:30]}') — trying tap approach")
        except Exception as e:
            self.logger.debug(f"Direct set_text failed for {field_name}: {e}")

        # ── 2. Raw coordinate tap pour forcer le focus ────────────────────
        # element.click() passe par accessibility et est bloqué sur enabled=false ;
        # device.click(x, y) envoie un vrai touch event qui bypass ce flag.
        cx, cy = 0, 0
        try:
            # Préférer element.bounds() qui est disponible sur XPathSelector
            b = element.bounds()
            cx = (b.left + b.right) // 2
            cy = (b.top + b.bottom) // 2
        except Exception:
            try:
                info = element.info
                bounds = info.get('bounds', {})
                cx = (bounds.get('left', 0) + bounds.get('right', 0)) // 2
                cy = (bounds.get('top', 0) + bounds.get('bottom', 0)) // 2
            except Exception:
                pass

        if cx and cy:
            self.device.click(cx, cy)
            time.sleep(0.8)
        else:
            try:
                element.click()
                time.sleep(0.8)
            except Exception:
                pass

        self._dismiss_autofill_dropdown()

        # Effacer le contenu existant
        existing_text = ""
        try:
            existing_text = element.get_text() or ""
        except Exception:
            pass

        if existing_text:
            self.logger.debug(f"Clearing pre-filled text '{existing_text[:20]}'...")
            cleared = False
            try:
                element.set_text("")
                time.sleep(0.25)
                cleared = True
            except Exception as e:
                self.logger.debug(f"set_text('') failed: {e}")

            if not cleared:
                self.device.press("ctrl+a")
                time.sleep(0.15)
                self.device.press("delete")
                time.sleep(0.15)
                self.device.press("ctrl+a")
                time.sleep(0.1)
                self.device.press("delete")
                time.sleep(0.2)

            self._dismiss_autofill_dropdown()

            # Re-tap pour récupérer le focus après l'effacement
            cx2, cy2 = cx, cy  # réutilise les coordonnées calculées plus haut
            if cx2 and cy2:
                self.device.click(cx2, cy2)
                time.sleep(0.4)
            else:
                try:
                    element.click()
                    time.sleep(0.4)
                except Exception:
                    pass

        if self.text_actions.type_text(text, clear_first=False, human_typing=True):
            self.logger.success(f"✅ {field_name} filled")
            return True

        self.logger.error(f"❌ Failed to fill {field_name}")
        return False

    def _clear_username_and_fill(self, element, username: str) -> bool:
        """
        Remplit le champ username en utilisant le bouton X/effacer si le champ est pré-rempli.

        Stratégie :
        1. Tap brut (device.click) pour focaliser le champ (fait apparaître le bouton X)
        2. Si texte pré-rempli → clic sur le bouton X/effacer (ou ctrl+a/delete en fallback)
        3. set_text() direct via l'accessibility service (le plus fiable pour champ vide/vidé)
        4. Fallback type_text() (ADB keyboard) si set_text échoue
        """
        # Calculer les coordonnées du champ pour le tap brut
        cx, cy = 0, 0
        try:
            b = element.bounds()
            cx = (b.left + b.right) // 2
            cy = (b.top + b.bottom) // 2
        except Exception:
            try:
                info = element.info
                bounds = info.get('bounds', {})
                cx = (bounds.get('left', 0) + bounds.get('right', 0)) // 2
                cy = (bounds.get('top', 0) + bounds.get('bottom', 0)) // 2
            except Exception:
                pass

        # Tap brut pour focaliser (bypass enabled=false, fait apparaître le bouton X)
        if cx and cy:
            self.device.click(cx, cy)
        else:
            try:
                element.click()
            except Exception as e:
                self.logger.debug(f"Tap to focus username field failed: {e}")
        time.sleep(0.6)
        self._dismiss_autofill_dropdown()

        # Re-tap pour restaurer le focus si l'autofill a été dismissé avec BACK
        if cx and cy:
            self.device.click(cx, cy)
            time.sleep(0.4)

        # Vérifier si le champ est pré-rempli
        existing_text = ""
        try:
            existing_text = element.get_text() or ""
        except Exception:
            pass

        if existing_text:
            self.logger.info(f"🧹 Pre-filled username detected: '{existing_text}' — clearing with X button...")
            cleared = False

            # Essayer le bouton X/effacer (apparaît quand le champ est focalisé)
            for selector in self.auth_selectors.username_clear_button:
                try:
                    clear_btn = self.device.xpath(selector)
                    if clear_btn.exists:
                        clear_btn.click()
                        time.sleep(0.4)
                        cleared = True
                        self.logger.info("✅ X/clear button clicked successfully")
                        break
                    else:
                        self.logger.info(f"   X button not found: {selector}")
                except Exception as e:
                    self.logger.info(f"   X button selector error: {selector} ({e})")

            if not cleared:
                # Fallback : ctrl+a / delete
                self.logger.info("⚠️ No X button found — using ctrl+a/delete fallback")
                self.device.press("ctrl+a")
                time.sleep(0.15)
                self.device.press("delete")
                time.sleep(0.15)
                self.device.press("ctrl+a")
                time.sleep(0.1)
                self.device.press("delete")
                time.sleep(0.2)

            self._dismiss_autofill_dropdown()

            # Re-tap pour récupérer le focus après l'effacement
            if cx and cy:
                self.device.click(cx, cy)
                time.sleep(0.4)

        # ── Saisir le username ────────────────────────────────────────────
        # Stratégie 1 : set_text via accessibility (le plus direct, pas besoin de clavier)
        self.logger.info(f"⌨️ Typing username '{username}' via set_text...")
        try:
            element.set_text(username)
            time.sleep(0.5)
            self._dismiss_autofill_dropdown()
            actual = ""
            try:
                actual = element.get_text() or ""
            except Exception:
                pass
            self.logger.info(f"🔍 Post-set_text field value: '{actual}' (expected: '{username}')")
            if username.strip() in actual or actual.strip() == username.strip():
                self.logger.info(f"✅ Username confirmed in field: '{actual}'")
                return True
            self.logger.info(f"⚠️ set_text verification failed: got '{actual}' — falling back to type_text")
        except Exception as e:
            self.logger.info(f"set_text failed for username: {e}")

        # Stratégie 2 : Taktik keyboard (nécessite focus clavier actif)
        # Re-tap pour s'assurer que le focus est bien sur le champ
        self.logger.info(f"⌨️ Typing username '{username}' via ADB keyboard (type_text)...")
        if cx and cy:
            self.device.click(cx, cy)
            time.sleep(0.4)
        if self.text_actions.type_text(username, clear_first=False, human_typing=True):
            # Vérifier ce qu'il y a dans le champ après type_text
            try:
                actual_after = element.get_text() or ""
                self.logger.info(f"✅ Username filled via type_text — field now contains: '{actual_after}'")
            except Exception:
                self.logger.info("✅ Username filled via type_text (can't read back field)")
            return True

        self.logger.error("❌ Failed to fill username field")
        return False

    def _fill_credentials(self, username: str, password: str) -> bool:
        """
        Remplit les champs username et password.

        Args:
            username: Nom d'utilisateur
            password: Mot de passe

        Returns:
            True si succès, False sinon
        """
        self.logger.info("📝 Filling credentials...")

        # Chercher le champ username éditable (EditText).
        # S'il n'est pas présent, on est sur un écran "password-only" (compte pré-sélectionné)
        # et Instagram affiche juste le nom du compte en View non-éditable.
        username_found = False
        username_filled = False
        for selector in self.auth_selectors.username_field:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    username_found = True
                    try:
                        pre_text = element.get_text() or ''
                    except Exception:
                        pre_text = '?'
                    self.logger.info(f"⌨️ Found username field (selector: {selector}) — current value: '{pre_text}'")
                    if self._clear_username_and_fill(element, username):
                        username_filled = True
                        break
            except Exception as e:
                self.logger.debug(f"Failed with selector {selector}: {e}")
                continue

        if username_found and not username_filled:
            self.logger.error("❌ Username field found but failed to fill it")
            return False
        elif not username_found:
            # Pas d'EditText username visible → écran password-only (compte pré-sélectionné par Instagram).
            # CRITIQUE : vérifier que c'est bien le bon compte affiché avant de remplir le mot de passe.
            self.logger.info(f"📱 No username EditText — checking which account is shown on password-only screen...")
            account_confirmed = False
            for sel in self.auth_selectors.password_only_account_selectors(username):
                try:
                    if self.device.xpath(sel).exists:
                        account_confirmed = True
                        self.logger.info(f"✅ Correct account '@{username}' confirmed on password-only screen")
                        break
                except Exception:
                    pass

            if not account_confirmed:
                self.logger.warning(f"⚠️ Password-only screen but '@{username}' NOT found on screen — wrong account pre-selected! Pressing Back to reset.")
                self.device.press("back")
                time.sleep(1.5)
                return False

            self.logger.info(f"📱 Password-only screen confirmed for @{username} — skipping username field")

        # Petit délai entre les champs
        time.sleep(self.utils.generate_human_like_delay(0.5, 1.0))

        # Remplir le champ password
        password_filled = False
        for selector in self.auth_selectors.password_field:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    self.logger.debug(f"Found password field with selector: {selector}")
                    if self._clear_and_fill_field(element, password, "Password"):
                        password_filled = True
                        break
            except Exception as e:
                self.logger.debug(f"Failed with selector {selector}: {e}")
                continue

        if not password_filled:
            self.logger.error("❌ Failed to fill password")
            return False

        return True
    
    def _click_login_button(self) -> bool:
        """
        Clique sur le bouton de connexion.
        
        Returns:
            True si succès, False sinon
        """
        self.logger.info("👆 Clicking login button...")
        
        # Petit délai avant de cliquer
        time.sleep(self.utils.generate_human_like_delay(0.5, 1.0))
        
        if self._click_first_match(self.auth_selectors.login_button, "Login button"):
            return True
        
        self.logger.error("❌ Failed to click login button")
        return False
