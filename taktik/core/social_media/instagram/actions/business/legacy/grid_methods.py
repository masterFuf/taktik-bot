import time
import random
import re
from typing import Dict, List, Any
from loguru import logger


class LegacyGridLikeMethods:
    
    def __init__(self, device, selectors, profile_selectors, post_selectors, 
                 navigation_selectors, debug_selectors, problematic_page_detector):
        self.device = device
        self.selectors = selectors
        self.profile_selectors = profile_selectors
        self.post_selectors = post_selectors
        self.navigation_selectors = navigation_selectors
        self.debug_selectors = debug_selectors
        self.problematic_page_detector = problematic_page_detector
        self.logger = logger.bind(module="legacy-grid-like")
    
    def _like_posts_with_advanced_logic(self, username: str, max_likes: int, config: Dict[str, Any], profile_info: Dict[str, Any] = None) -> int:

        try:
            posts_liked = 0
            
            total_scrolls = self._calculate_scroll_count(profile_info)
            
            scrolls_done = 0
            
            empty_attempts = 0
            max_empty_attempts = 5
            failed_like_attempts = 0
            max_failed_like_attempts = 10
            processed_posts = set()
            
            consecutive_all_processed = 0
            max_consecutive_all_processed = 3
            
            while posts_liked < max_likes and scrolls_done <= total_scrolls and empty_attempts < max_empty_attempts and failed_like_attempts < max_failed_like_attempts and consecutive_all_processed < max_consecutive_all_processed:
                if scrolls_done < total_scrolls:
                    scrolls_this_round = min(
                        random.choice([1, 2]),
                        total_scrolls - scrolls_done
                    )
                    
                    self.logger.info(f"📜 [SCROLL] {scrolls_this_round} scroll(s) pour diversifier (progression: {scrolls_done + scrolls_this_round}/{total_scrolls})")
                    self._perform_scrolls(scrolls_this_round)
                    scrolls_done += scrolls_this_round
                    
                    time.sleep(random.uniform(1.5, 2.5))
                
                remaining_likes = max_likes - posts_liked
                if remaining_likes <= 0:
                    break
                    
                posts_this_round = min(remaining_likes, random.randint(1, 2))
                
                self.logger.info(f"🔍 Détection des posts cliquables (chercher {posts_this_round} posts)")
                posts_elements = self._find_clickable_posts(posts_this_round * 3)
                
                if not posts_elements:
                    empty_attempts += 1
                    self.logger.warning(f"⚠️ Aucun post cliquable trouvé à cette position (tentative vide {empty_attempts}/{max_empty_attempts})")
                    
                    if empty_attempts >= max_empty_attempts:
                        self.logger.error(f"❌ Arrêt après {max_empty_attempts} tentatives vides - profil ne contient probablement pas de posts likables")
                        break
                    
                    continue
                
                empty_attempts = 0
                
                self.logger.success(f"✅ Trouvé {len(posts_elements)} posts cliquables")
                selected_posts = self._select_posts_from_different_rows(posts_elements, posts_this_round)
                
                new_posts = []
                for post in selected_posts:
                    try:
                        bounds = post.info.get('bounds', {})
                        post_signature = f"{bounds.get('left', 0)},{bounds.get('top', 0)},{bounds.get('right', 0)},{bounds.get('bottom', 0)}"
                        
                        if post_signature not in processed_posts:
                            new_posts.append(post)
                            processed_posts.add(post_signature)
                            self.logger.debug(f"🆕 Nouveau post détecté: {post_signature}")
                        else:
                            self.logger.debug(f"🔄 Post déjà traité ignoré: {post_signature}")
                    except Exception as e:
                        new_posts.append(post)
                        self.logger.debug(f"⚠️ Erreur signature post, traitement quand même: {e}")
                
                selected_posts = new_posts
                
                if not selected_posts:
                    consecutive_all_processed += 1
                    self.logger.warning(f"⚠️ Tous les posts de cette position ont déjà été traités (tentative {consecutive_all_processed}/{max_consecutive_all_processed})")
                    empty_attempts += 1
                    
                    if consecutive_all_processed >= max_consecutive_all_processed:
                        self.logger.error(f"❌ BOUCLE INFINIE DÉTECTÉE - Tous les posts sont déjà traités depuis {consecutive_all_processed} tentatives consécutives")
                        break
                    
                    continue
                
                consecutive_all_processed = 0
                self.logger.info(f"Sélection de {len(selected_posts)} nouveaux posts à liker à cette position")
                
                for i, post_element in enumerate(selected_posts):
                    if posts_liked >= max_likes:
                        break
                        
                    try:
                        self.logger.info(f"🎯 TRAITEMENT POST #{posts_liked + 1}/{max_likes}")
                        
                        if self._click_on_post_element(post_element, i + 1):
                            time.sleep(2)
                            
                            if self._is_post_already_liked():
                                self.logger.info(f"Post déjà liké, ignoré")
                                failed_like_attempts = 0  # Reset car post trouvé mais déjà liké
                            else:
                                if self._like_current_post_advanced():
                                    posts_liked += 1
                                    failed_like_attempts = 0  # Reset compteur d'échecs
                                    self.logger.info(f"Nouveau post de {username} liké avec succès ({posts_liked}/{max_likes})")
                                    
                                    delay = random.uniform(*config['like_delay_range'])
                                    time.sleep(delay)
                                else:
                                    failed_like_attempts += 1
                                    self.logger.warning(f"⚠️ Échec du like #{failed_like_attempts}/{max_failed_like_attempts} - bouton like non trouvé")
                            
                            self._return_to_grid()
                        else:
                            failed_like_attempts += 1
                            self.logger.warning(f"⚠️ Échec du clic sur post #{failed_like_attempts}/{max_failed_like_attempts}")
                        
                    except Exception as e:
                        self.logger.error(f"Erreur lors du traitement du post: {e}")
                        continue
            
            if posts_liked >= max_likes:
                self.logger.success(f"✅ [FINAL] {posts_liked}/{max_likes} posts likés avec {scrolls_done} scrolls - objectif atteint")
            elif consecutive_all_processed >= max_consecutive_all_processed:
                self.logger.error(f"❌ [FINAL] {posts_liked}/{max_likes} posts likés - BOUCLE INFINIE détectée (tous posts déjà traités {consecutive_all_processed} fois)")
            elif failed_like_attempts >= max_failed_like_attempts:
                self.logger.error(f"❌ [FINAL] {posts_liked}/{max_likes} posts likés - arrêt après {failed_like_attempts} échecs consécutifs")
            elif empty_attempts >= max_empty_attempts:
                self.logger.warning(f"⚠️ [FINAL] {posts_liked}/{max_likes} posts likés - arrêt après {empty_attempts} tentatives vides (tous posts traités)")
            elif scrolls_done > total_scrolls:
                self.logger.info(f"ℹ️ [FINAL] {posts_liked}/{max_likes} posts likés - fin du scroll ({scrolls_done}/{total_scrolls})")
            else:
                self.logger.info(f"ℹ️ [FINAL] {posts_liked}/{max_likes} posts likés avec {scrolls_done} scrolls")
            
            self.logger.info(f"📊 Posts traités au total: {len(processed_posts)}")
            
            return posts_liked
            
        except Exception as e:
            self.logger.error(f"Erreur dans _like_posts_with_advanced_logic: {e}")
            return 0
    
    def _calculate_scroll_count(self, profile_info: Dict[str, Any] = None) -> int:
        try:
            from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
            detection = DetectionActions(self.device)
            visible_posts = detection.count_visible_posts()
            
            total_posts = 0
            if profile_info and 'posts_count' in profile_info:
                total_posts = profile_info.get('posts_count', 0)
                self.logger.info(f"📊 [PROFIL] Total posts: {total_posts}, Visibles: {visible_posts}")
            else:
                self.logger.warning(f"⚠️ [PROFIL] Pas d'info profil disponible - fallback sur posts visibles: {visible_posts}")
            
            if total_posts <= 6:
                scroll_count = 0
                self.logger.info(f"🎯 [SCROLL] Profil avec {total_posts} posts - pas de scroll nécessaire")
            elif total_posts <= 20:
                scroll_count = random.randint(1, 2)
                self.logger.info(f"🎯 [SCROLL] Profil avec {total_posts} posts - scroll léger: {scroll_count} scrolls")
            elif total_posts <= 100:
                scroll_count = random.randint(2, 4)
                self.logger.info(f"🎯 [SCROLL] Profil avec {total_posts} posts - scroll modéré: {scroll_count} scrolls")
            else:
                scroll_count = random.randint(3, 7)
                self.logger.info(f"🎯 [SCROLL] Profil avec {total_posts} posts - scroll important: {scroll_count} scrolls")
            
            if total_posts == 0:
                if visible_posts <= 3:
                    scroll_count = 0
                    self.logger.info(f"🎯 [SCROLL] Seulement {visible_posts} posts visibles - pas de scroll nécessaire")
                elif visible_posts <= 6:
                    scroll_count = random.randint(1, 2)
                    self.logger.info(f"🎯 [SCROLL] {visible_posts} posts visibles - scroll léger: {scroll_count} scrolls")
                elif visible_posts <= 9:
                    scroll_count = random.randint(2, 4)
                    self.logger.info(f"🎯 [SCROLL] {visible_posts} posts visibles - scroll modéré: {scroll_count} scrolls")
                else:
                    scroll_count = random.randint(3, 6)
                    self.logger.info(f"🎯 [SCROLL] {visible_posts} posts visibles - scroll complet: {scroll_count} scrolls")
            
            return scroll_count
            
        except Exception as e:
            self.logger.error(f"Erreur calcul nombre de scrolls: {e}")
            return 0
    
    def _perform_scrolls(self, count: int):
        try:
            for i in range(count):
                from taktik.core.social_media.instagram.actions.core.device_facade import Direction
                self.device.swipe(Direction.UP, scale=0.6)
                
                pause = random.uniform(0.8, 1.5)
                self.logger.debug(f"📜 [SCROLL] Swipe {i+1}/{count} - pause {pause:.1f}s")
                time.sleep(pause)
                
        except Exception as e:
            self.logger.error(f"Erreur lors des scrolls: {e}")
    
    def _seems_like_private_profile(self) -> bool:
        try:
            for selector in self.profile_selectors.zero_posts_indicators:
                if self.device.xpath(selector).exists:
                    self.logger.debug(f"🔍 Profil avec 0 publications détecté: {selector}")
                    return True
            
            for selector in self.profile_selectors.private_indicators:
                if self.device.xpath(selector).exists:
                    self.logger.debug(f"🔍 Indicateur de profil privé trouvé: {selector}")
                    return True
            
            follow_buttons = self.device.xpath(self.profile_selectors.follow_buttons).all()
            if len(follow_buttons) >= 2:
                self.logger.debug(f"🔍 Écran de suggestions détecté: {len(follow_buttons)} boutons Follow")
                return True
                
            suivre_buttons = self.device.xpath(self.profile_selectors.suivre_buttons).all()
            if len(suivre_buttons) >= 2:
                self.logger.debug(f"🔍 Écran de suggestions détecté: {len(suivre_buttons)} boutons Suivre")
                return True
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Erreur détection profil privé alternative: {e}")
            return False
    
    def _find_clickable_posts(self, max_posts: int) -> List:
        try:
            from taktik.core.social_media.instagram.actions.atomic.detection_actions import DetectionActions
            detection = DetectionActions(self.device)
            
            if not detection.is_on_profile_screen():
                self.logger.error("❌ Pas sur un écran de profil, impossible de trouver les posts")
                return []
            
            self.logger.debug("✅ Confirmé: nous sommes sur un écran de profil")
            
            is_private = detection.is_private_account()
            self.logger.debug(f"🔍 [DEBUG] is_private_account() retourne: {is_private}")
            
            visible_posts_count = detection.count_visible_posts()
            self.logger.debug(f"🔍 [DEBUG] Posts visibles: {visible_posts_count}")
            
            if is_private or (visible_posts_count == 0 and self._seems_like_private_profile()):
                self.logger.warning("🔒 Profil privé détecté - impossible d'accéder aux posts")
                return []
            
            posts_selector = '//*[@resource-id="com.instagram.android:id/image_button"]'
            
            self.logger.debug(f"Test sélecteur principal: {posts_selector}")
            posts = self.device.xpath(posts_selector).all()
            
            if not posts:
                self.logger.warning("Aucun post trouvé avec le sélecteur image_button")
                self._ensure_on_posts_tab()
                posts = self.device.xpath(posts_selector).all()
                
            if not posts:
                self.logger.error("❌ Toujours aucun post trouvé après vérification de l'onglet")
                return []
            
            self.logger.info(f"Trouvé {len(posts)} posts avec sélecteur")
            
            valid_posts = []
            for i, post in enumerate(posts[:max_posts]):
                if self._is_valid_post_element(post, i + 1):
                    valid_posts.append(post)
            
            self.logger.info(f"Détection terminée: {len(valid_posts)} posts cliquables trouvés")
            return valid_posts
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la détection des posts: {e}")
            return []
    
    def _is_valid_post_element(self, post_element, position: int) -> bool:
        try:
            self.logger.debug(f"🔍 Post #{position}: Type = {type(post_element)}, Attributs = {dir(post_element)[:10]}...")
            
            if hasattr(post_element, 'info'):
                bounds = post_element.info.get('bounds', {})
                self.logger.debug(f"🔍 Post #{position}: Bounds depuis .info = {bounds}")
            
            if hasattr(post_element, 'bounds'):
                bounds_str = str(post_element.bounds)
                self.logger.debug(f"🔍 Post #{position}: Bounds string = '{bounds_str}'")
                
                import re
                left, top, right, bottom = None, None, None, None
                
                match1 = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
                if match1:
                    left, top, right, bottom = map(int, match1.groups())
                    self.logger.debug(f"🔍 Format [x,y][x,y] détecté")
                
                match2 = re.match(r'\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', bounds_str)
                if match2:
                    left, top, right, bottom = map(int, match2.groups())
                    self.logger.debug(f"🔍 Format (x, y, x, y) détecté")
                
                if left is not None:
                    width = right - left
                    height = bottom - top
                    
                    self.logger.debug(f"🔍 Post #{position}: Dimensions = {width}x{height}px")
                    
                    if width > 200 and height > 100:  # Retourné à 100px comme avant
                        self.logger.debug(f"✅ Post #{position} validé ({width}x{height}px)")
                        return True
                    else:
                        self.logger.debug(f"❌ Post #{position} rejeté: trop petit ({width}x{height}px)")
                else:
                    self.logger.debug(f"❌ Post #{position}: Format bounds non reconnu")
            
            if hasattr(post_element, 'info'):
                bounds = post_element.info.get('bounds', {})
                if bounds:
                    width = bounds.get('right', 0) - bounds.get('left', 0)
                    height = bounds.get('bottom', 0) - bounds.get('top', 0)
                    
                    self.logger.debug(f"🔍 Post #{position}: Fallback dimensions = {width}x{height}px")
                    
                    if width > 200 and height > 100:
                        self.logger.debug(f"✅ Post #{position} validé via fallback ({width}x{height}px)")
                        return True
            
            self.logger.debug(f"❌ Post #{position}: Aucune méthode de validation réussie")
            return False
            
        except Exception as e:
            self.logger.debug(f"Erreur validation post #{position}: {e}")
            return False
    
    def _select_posts_from_different_rows(self, posts_elements: List, max_likes: int) -> List:
        try:
            if not posts_elements:
                return []
            
            rows = {}
            for i, post in enumerate(posts_elements):
                try:
                    if hasattr(post, 'info'):
                        y_coord = post.info.get('bounds', {}).get('top', 0)
                        row_y = (y_coord // 50) * 50
                        
                        if row_y not in rows:
                            rows[row_y] = []
                        rows[row_y].append(post)
                        
                        self.logger.debug(f"📁 [RANGEE] Post #{i+1} -> Rangée Y={row_y} (coord exacte: {y_coord})")
                except Exception as e:
                    self.logger.debug(f"Erreur groupement post #{i+1}: {e}")
                    continue
            
            self.logger.info(f"📁 [RANGEES] {len(rows)} rangées détectées:")
            for row_y, posts in rows.items():
                self.logger.info(f"  • Rangée Y={row_y}: {len(posts)} posts")
            
            selected_posts = []
            for row_y in sorted(rows.keys()):
                if len(selected_posts) >= max_likes:
                    break
                
                row_posts = rows[row_y]
                selected_post = random.choice(row_posts)
                selected_posts.append(selected_post)
                
                self.logger.info(f"✅ [SELECTION] Post sélectionné depuis rangée Y={row_y}")
            
            if len(selected_posts) < max_likes:
                remaining_needed = max_likes - len(selected_posts)
                self.logger.info(f"🔄 [COMPLETION] Besoin de {remaining_needed} posts supplémentaires")
                all_remaining_posts = []
                for posts in rows.values():
                    for post in posts:
                        if post not in selected_posts:
                            all_remaining_posts.append(post)
                
                additional_posts = random.sample(
                    all_remaining_posts, 
                    min(remaining_needed, len(all_remaining_posts))
                )
                selected_posts.extend(additional_posts)
                
                for post in additional_posts:
                    self.logger.info("➕ [COMPLETION] Post ajouté")
            
            self.logger.success(f"✅ [FINAL] {len(selected_posts)} posts sélectionnés avec diversité de rangées")
            return selected_posts
            
        except Exception as e:
            self.logger.error(f"Erreur sélection posts par rangées: {e}")
            return posts_elements[:max_likes]  # Fallback
    
    def _click_on_post_element(self, post_element, position: int) -> bool:
        try:
            page_result = self.problematic_page_detector.detect_and_handle_problematic_pages()
            if page_result.get('detected'):
                self.logger.warning(f"🚨 Page problématique détectée avant clic: {page_result.get('page_type')}")
                if page_result.get('soft_ban'):
                    self.logger.error("🛑 Soft ban détecté - arrêt nécessaire")
                    return False
                if not page_result.get('closed'):
                    self.logger.error("❌ Impossible de fermer la popup - arrêt du clic")
                    return False
            
            if hasattr(post_element, 'info'):
                bounds = post_element.info.get('bounds', {})
                resource_id = post_element.info.get('resourceName', 'unknown')
                self.logger.info(f"📍 [CLIC-POST] 🎯 POST #{position} - ResourceID: {resource_id}, Bounds: {bounds}")
            
            # Vérifier que l'élément existe encore
            if hasattr(post_element, 'exists') and not post_element.exists:
                self.logger.warning(f"Post #{position} n'est plus accessible")
                return False
            
            post_element.click()
            self.logger.debug(f"Clic sur le post #{position}...")
            time.sleep(1.5)  
            
            page_result = self.problematic_page_detector.detect_and_handle_problematic_pages()
            if page_result.get('detected'):
                self.logger.warning(f"🚨 Page problématique détectée après clic: {page_result.get('page_type')}")
                if page_result.get('soft_ban'):
                    self.logger.error("🛑 Soft ban détecté - arrêt nécessaire")
                    return False
                if not page_result.get('closed'):
                    self.logger.error("❌ Impossible de fermer la popup après clic")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur clic post #{position}: {e}")
            return False
    
    def _like_current_post_advanced(self) -> bool:
        try:
            like_selectors = self.post_selectors.like_button_advanced_selectors
            
            for selector in like_selectors:
                like_button = self.device.xpath(selector)
                if like_button.exists:
                    like_button.click()
                    self.logger.debug(f"✅ Like effectué avec succès (sélecteur: {selector[:50]}...)")
                    return True
            
            self.logger.warning("Bouton like non trouvé avec tous les sélecteurs")
            return False
                
        except Exception as e:
            self.logger.error(f"Erreur lors du like: {e}")
            return False
            
        except Exception as e:
            self.logger.error(f"Erreur retour à la grille: {e}")
    
    def _is_post_already_liked(self) -> bool:
        try:
            self.logger.info("Vérification si le post est déjà liké...")
            
            from ....ui.selectors import DETECTION_SELECTORS
            liked_selectors = DETECTION_SELECTORS.liked_button_indicators
            
            for selector in liked_selectors:
                if self.device.xpath(selector).exists:
                    self.logger.info("Le post est déjà liké")
                    return True
            
            self.logger.info("Le post n'est pas encore liké")
            return False
            
        except Exception as e:
            self.logger.debug(f"Erreur lors de la vérification: {e}")
            self.logger.info("Le post n'est pas encore liké")
            return False
    
    def _ensure_on_posts_tab(self):
        try:
            self.logger.debug("🔍 Vérification de l'onglet actuel...")
            
            for selector in self.navigation_selectors.posts_tab_options:
                posts_tab = self.device.xpath(selector)
                if posts_tab.exists:
                    self.logger.debug(f"✅ Onglet Posts trouvé avec: {selector}")
                    posts_tab.click()
                    self._human_like_delay('tab_switch')
                    self.logger.info("📋 Navigation vers l'onglet Posts effectuée")
                    return True
            
            self.logger.warning("⚠️ Impossible de trouver l'onglet Posts")
            return False
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la navigation vers l'onglet Posts: {e}")
            return False
    
    def _click_back_button(self):
        for selector in self.navigation_selectors.back_buttons:
            if self.device.xpath(selector).exists:
                self.logger.debug(f"Bouton back trouvé avec: {selector}")
                self.device.xpath(selector).click()
                return True
        
        self.logger.debug("Aucun bouton back trouvé")
        return False
    
    def _swipe_down_to_return(self):
        from taktik.core.social_media.instagram.actions.core.device_facade import Direction
        self.device.swipe(Direction.DOWN, scale=0.5)