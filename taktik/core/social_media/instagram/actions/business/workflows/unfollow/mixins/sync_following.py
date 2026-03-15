"""Sync Following mixin — incremental following list sync + non-follower detection.

Strategy:
- Following list: sort by "Date followed: Latest", scroll until we hit a known username → STOP
- Non-followers: click the native "People you don't follow back" category in the Followers tab
  → gives us the list directly without visiting each profile

This avoids:
- Full follower list rescroll (no sort available on followers)
- Visiting each profile to check follow-back status
"""

import json
import time
import random
from typing import Dict, Any, List, Optional, Set

from ....common.database_helpers import DatabaseHelpers
from taktik.core.database import get_db_service


class SyncFollowingMixin:
    """Mixin: sync the following list incrementally and detect non-followers via native category."""

    # ─── Public entry points ──────────────────────────────────────────────────

    def sync_following_list(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Sync incrémentale de la liste des followings.

        1. Ouvrir Following → trier "Date followed: Latest"
        2. Scroll + extraire les usernames
        3. Pour chaque username:
           - Si déjà en BDD (vu récemment) → STOP
           - Sinon → UPSERT dans following_sync

        Args:
            config: Configuration (optionnel)

        Returns:
            Dict avec new_count, total_count, stopped_early
        """
        config = config or {}
        mode = config.get('mode', 'fast')
        stats = {
            'new_count': 0,
            'updated_count': 0,
            'total_seen': 0,
            'stopped_early': False,
            'success': False,
        }

        try:
            account_id = self._get_account_id()
            if not account_id:
                self.logger.warning("sync_following_list: no account_id, skipping sync")
                return stats

            self.logger.info("🔄 Starting incremental following sync")

            # Naviguer vers son propre profil
            if not self.nav_actions.navigate_to_profile_tab():
                self.logger.error("sync_following_list: failed to navigate to profile tab")
                return stats
            time.sleep(2)

            # Ouvrir la liste Following
            if not self.nav_actions.open_following_list():
                self.logger.error("sync_following_list: failed to open following list")
                return stats
            time.sleep(1.5)

            # Trier par "Date followed: Latest" pour détecter les nouveaux en premier
            self._set_following_list_sort('latest')
            time.sleep(1.5)

            # Récupérer les usernames déjà connus en BDD pour détecter le point d'arrêt
            known_usernames = DatabaseHelpers.get_following_sync_usernames(account_id)
            self.logger.info(f"📋 {len(known_usernames)} known followings in DB")

            # For enriched mode, create a ProfileExtraction instance
            profile_extractor = None
            if mode == 'enriched':
                from ....management.profile.extraction import ProfileExtraction
                profile_extractor = ProfileExtraction(self.device, getattr(self, 'session_manager', None))

            d = self.device.device
            username_resource_id = 'com.instagram.android:id/follow_list_username'

            seen_on_screen: Set[str] = set()
            scroll_attempts = 0
            max_scrolls = 60  # Sécurité anti-boucle infinie
            stop_signal = False

            while scroll_attempts < max_scrolls and not stop_signal:
                # Récupérer les éléments visibles avec leurs références UI
                username_elements = d(resourceId=username_resource_id)
                if not username_elements.exists:
                    break

                new_found = False
                count = username_elements.count
                for i in range(count):
                    try:
                        el = username_elements[i]
                        username = (el.get_text() or '').strip().lstrip('@')
                        if not username or not self._is_valid_username(username):
                            continue
                    except Exception:
                        continue

                    if username in seen_on_screen:
                        continue
                    seen_on_screen.add(username)
                    stats['total_seen'] += 1
                    new_found = True

                    # Récupérer le display_name (subtitle)
                    display_name = ''
                    try:
                        subtitle_els = d(resourceId='com.instagram.android:id/follow_list_subtitle')
                        if subtitle_els.exists and i < subtitle_els.count:
                            display_name = subtitle_els[i].get_text() or ''
                    except Exception:
                        pass

                    # Si on rencontre un username déjà connu
                    if username in known_usernames:
                        # En mode fast : on s'arrête dès qu'on retrouve un connu
                        if mode != 'enriched':
                            try:
                                print(json.dumps({
                                    "type": "sync_user_discovered",
                                    "list_type": "following",
                                    "username": username,
                                    "display_name": display_name,
                                    "is_new": False,
                                }), flush=True)
                            except Exception:
                                pass
                            self.logger.info(
                                f"⏹ Found known username @{username} — stopping sync "
                                f"({stats['new_count']} new accounts added)"
                            )
                            stop_signal = True
                            stats['stopped_early'] = True
                            break
                        self.logger.debug(f"Known @{username} — processing anyway (enriched mode)")

                    # Following → upsert en BDD
                    is_bot_follow = DatabaseHelpers.has_bot_follow_record(username, account_id)
                    result = DatabaseHelpers.sync_following_upsert(
                        username=username,
                        display_name=display_name,
                        account_id=account_id,
                        followed_by_bot=is_bot_follow,
                    )
                    if result == 'new':
                        stats['new_count'] += 1
                        self.logger.debug(f"➕ New following: @{username}")
                    else:
                        stats['updated_count'] += 1

                    # Emit per-username IPC
                    try:
                        print(json.dumps({
                            "type": "sync_user_discovered",
                            "list_type": "following",
                            "username": username,
                            "display_name": display_name,
                            "is_new": result == 'new',
                        }), flush=True)
                    except Exception:
                        pass

                    # ── Enrichissement inline (comme likers_scraping) ──
                    if mode == 'enriched' and profile_extractor:
                        try:
                            self.logger.debug(f"🔍 Enriching @{username}...")
                            el.click()
                            time.sleep(random.uniform(1.5, 2.5))

                            info = profile_extractor.get_complete_profile_info(
                                username=username,
                                navigate_if_needed=False,
                                enrich=True,
                            )

                            if info:
                                self.logger.debug(
                                    f"✅ Enriched @{username}: "
                                    f"{info.get('followers_count', '?')} followers"
                                )
                                try:
                                    print(json.dumps({
                                        "type": "sync_user_enriched",
                                        "list_type": "following",
                                        "username": username,
                                        "followers_count": info.get('followers_count', 0),
                                        "following_count": info.get('following_count', 0),
                                        "posts_count": info.get('posts_count', 0),
                                        "is_private": info.get('is_private', False),
                                    }), flush=True)
                                except Exception:
                                    pass

                            # Retour à la liste
                            d.press('back')
                            time.sleep(random.uniform(1.0, 1.5))

                            # Après back, les éléments UI sont invalidés → re-lire
                            break

                        except Exception as e:
                            self.logger.debug(f"Error enriching @{username}: {e}")
                            try:
                                d.press('back')
                                time.sleep(1)
                            except Exception:
                                pass
                            break  # Re-lire les éléments UI
                        # Ne pas continuer la boucle for après enrichissement
                        continue

                if stop_signal:
                    break

                if not new_found:
                    self.logger.info("No new accounts after scroll — end of following list")
                    break

                # Scroll seulement si pas en mode enrichi (en enrichi on re-scanne d'abord)
                if mode != 'enriched':
                    self._scroll_following_list()
                    time.sleep(1.5)
                    scroll_attempts += 1
                else:
                    # En mode enrichi, on a break après chaque profil enrichi
                    # Vérifier s'il reste des éléments non vus sur l'écran actuel
                    remaining = d(resourceId=username_resource_id)
                    has_unseen = False
                    if remaining.exists:
                        for j in range(remaining.count):
                            try:
                                u = (remaining[j].get_text() or '').strip().lstrip('@')
                                if u and u not in seen_on_screen:
                                    has_unseen = True
                                    break
                            except Exception:
                                continue
                    if not has_unseen:
                        self._scroll_following_list()
                        time.sleep(1.5)
                        scroll_attempts += 1

            stats['success'] = True
            self.logger.info(
                f"✅ Following sync complete: {stats['new_count']} new, "
                f"{stats['updated_count']} updated, {stats['total_seen']} seen"
            )


        except Exception as e:
            self.logger.error(f"Error in sync_following_list: {e}")

        return stats

    def scrape_non_followers_category(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Scraper la catégorie native "People you don't follow back" dans la vue Followers.

        Instagram nous donne directement cette liste filtrée — pas besoin de visiter
        chaque profil pour vérifier le follow-back.

        1. Naviguer vers la vue Followers
        2. Cliquer sur "People you don't follow back"
        3. Scroll + extraire tous les usernames
        4. Marquer is_follower_back = 0 dans following_sync pour ces usernames
        5. Les followings NON présents dans cette liste → is_follower_back = 1

        Args:
            config: Configuration (optionnel)

        Returns:
            Dict avec non_followers_count, mutuals_count, success
        """
        config = config or {}
        stats = {
            'non_followers_count': 0,
            'mutuals_count': 0,
            'success': False,
        }

        try:
            account_id = self._get_account_id()
            if not account_id:
                self.logger.warning("scrape_non_followers_category: no account_id")
                return stats

            self.logger.info("🔍 Scraping 'People you don't follow back' category")

            # Détecter si on est déjà dans la vue unifiée (après sync_following_list)
            d = self.device.device
            unified_layout = d.xpath('//*[@resource-id="com.instagram.android:id/unified_follow_list_tab_layout"]')

            if unified_layout.exists:
                # Vue unifiée ouverte — cliquer sur le tab "Followers"
                self.logger.debug("Already in unified follow list view, switching to Followers tab")
                followers_tab = d.xpath(
                    '//*[@resource-id="com.instagram.android:id/unified_follow_list_tab_layout"]'
                    '//*[contains(@text, "Followers")]'
                )
                if followers_tab.exists:
                    followers_tab.click()
                else:
                    self.logger.error("scrape_non_followers_category: Followers tab not found in unified view")
                    return stats
            else:
                # Pas dans la vue unifiée — naviguer depuis le profil
                self.logger.debug("Not in unified view, navigating from profile")
                if not self.nav_actions.navigate_to_profile_tab():
                    self.logger.error("scrape_non_followers_category: failed to navigate to profile")
                    return stats
                time.sleep(1)
                if not self.nav_actions.open_followers_list():
                    self.logger.error("scrape_non_followers_category: failed to open followers list")
                    return stats
            time.sleep(1.5)

            # Cliquer sur la catégorie "People you don't follow back"
            if not self._click_non_followers_category():
                self.logger.warning(
                    "scrape_non_followers_category: category not found — "
                    "may not be visible for this account size"
                )
                return stats

            # Attendre que la vue non-followers charge (bouton "Follow back" visible)
            follow_back_visible = False
            for wait in range(5):
                time.sleep(1)
                if d(resourceId='com.instagram.android:id/follow_list_row_large_follow_button', text='Follow back').exists:
                    follow_back_visible = True
                    self.logger.debug(f"Non-followers view loaded after {wait + 1}s")
                    break
            if not follow_back_visible:
                self.logger.warning("scrape_non_followers_category: non-followers view did not load (no 'Follow back' buttons)")
                return stats

            # Extraire tous les non-followers
            non_follower_usernames = self._extract_all_non_followers()
            stats['non_followers_count'] = len(non_follower_usernames)

            self.logger.info(f"📋 Found {len(non_follower_usernames)} non-followers")

            # Mettre à jour la BDD
            for username in non_follower_usernames:
                DatabaseHelpers.mark_not_follower_back(username, account_id)

            # Tous les followings en BDD qui ne sont PAS dans cette liste → mutuels
            all_followings = DatabaseHelpers.get_following_sync_usernames(account_id)
            non_followers_set = set(u.lower() for u in non_follower_usernames)

            all_followings_lower = {u.lower() for u in all_followings}

            for username in all_followings:
                if username.lower() not in non_followers_set:
                    DatabaseHelpers.mark_follower_back(username, account_id)
                    stats['mutuals_count'] += 1

            # ── Populate followers_sync ──
            # 1. Entries from "don't follow back" = confirmed followers
            fans_count = 0
            for username in non_follower_usernames:
                is_following = username.lower() in all_followings_lower
                DatabaseHelpers.sync_follower_upsert(
                    username=username,
                    account_id=account_id,
                    is_following_back=is_following,
                    source='non_followers_category',
                )
                if not is_following:
                    fans_count += 1

            # 2. Mutuals = our followings confirmed as followers too
            for username in all_followings:
                if username.lower() not in non_followers_set:
                    DatabaseHelpers.sync_follower_upsert(
                        username=username,
                        account_id=account_id,
                        is_following_back=True,
                        source='mutual_detection',
                    )

            stats['fans_count'] = fans_count
            stats['success'] = True
            self.logger.info(
                f"✅ Non-follower sync complete: {stats['non_followers_count']} non-followers, "
                f"{stats['mutuals_count']} mutuals, {fans_count} fans"
            )

            # Fermer la vue non-followers pour revenir à un état propre
            self.logger.debug("Closing non-followers view (back press)")
            self.device.device.press('back')
            time.sleep(1)

        except Exception as e:
            self.logger.error(f"Error in scrape_non_followers_category: {e}")

        return stats

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _get_visible_following_usernames_with_display(self) -> List[tuple]:
        """
        Extraire les (username, display_name) visibles dans la liste following.

        Returns:
            Liste de tuples (username, display_name)
        """
        results = []
        try:
            d = self.device.device
            username_resource_id = 'com.instagram.android:id/follow_list_username'
            subtitle_resource_id = 'com.instagram.android:id/follow_list_subtitle'

            username_elements = d(resourceId=username_resource_id)
            subtitle_elements = d(resourceId=subtitle_resource_id)

            if not username_elements.exists:
                return results

            count = username_elements.count
            for i in range(count):
                try:
                    username = username_elements[i].get_text() or ''
                    username = username.strip().lstrip('@')
                    if not username or not self._is_valid_username(username):
                        continue

                    display_name = ''
                    try:
                        if subtitle_elements.exists and i < subtitle_elements.count:
                            display_name = subtitle_elements[i].get_text() or ''
                    except Exception:
                        pass

                    results.append((username, display_name))
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Error extracting visible following accounts: {e}")

        return results

    def _click_non_followers_category(self) -> bool:
        """
        Cliquer sur la catégorie 'People you don't follow back'.

        D'après le dump XML, c'est un bouton avec:
        - content-desc="People you don't follow back"
        - resource-id="com.instagram.android:id/container"
        """
        try:
            d = self.device.device
            xpaths = [
                '//*[contains(@content-desc, "don\'t follow back")]',
                '//*[contains(@content-desc, "People you don")]',
                '//*[@resource-id="com.instagram.android:id/container"][contains(@content-desc, "follow")]',
                '//*[@resource-id="com.instagram.android:id/title"][contains(@text, "don\'t follow back")]',
                '//*[@resource-id="com.instagram.android:id/title"][contains(@text, "follow back")]',
            ]
            for i, xpath in enumerate(xpaths):
                el = d.xpath(xpath)
                if el.exists:
                    self.logger.debug(f"_click_non_followers_category: matched xpath #{i+1}: {xpath}")
                    el.click()
                    return True
            self.logger.debug("_click_non_followers_category: no xpath matched")
            return False

        except Exception as e:
            self.logger.debug(f"Error clicking non-followers category: {e}")
            return False

    def _extract_all_non_followers(self) -> List[str]:
        """
        Extraire tous les usernames de la liste 'People you don't follow back'.

        La liste n'a pas de tri, on scrolle jusqu'à la fin.
        Chaque item a un bouton "Follow back" (confirme qu'ils ne nous suivent pas).

        Returns:
            Liste complète des usernames non-followers
        """
        usernames = []
        seen: Set[str] = set()
        scroll_attempts = 0
        max_scrolls = 30

        while scroll_attempts < max_scrolls:
            visible = self._get_visible_non_follower_usernames()

            new_found = False
            for username in visible:
                if username not in seen:
                    seen.add(username)
                    usernames.append(username)
                    new_found = True

            if not new_found:
                self.logger.debug("No new non-followers after scroll — end of list")
                break

            self._scroll_following_list()
            time.sleep(1.2)
            scroll_attempts += 1

        return usernames

    def _get_visible_non_follower_usernames(self) -> List[str]:
        """
        Extraire les usernames visibles dans la vue 'People you don't follow back'.

        On vérifie la présence du bouton "Follow back" pour confirmer qu'on est
        dans la bonne vue (et non dans la liste Following standard).

        Returns:
            Liste des usernames visibles
        """
        results = []
        try:
            d = self.device.device
            username_resource_id = 'com.instagram.android:id/follow_list_username'

            # Vérifier qu'on est dans la bonne vue (bouton "Follow back" présent)
            follow_back_btn = d(
                resourceId='com.instagram.android:id/follow_list_row_large_follow_button',
                text='Follow back'
            )
            if not follow_back_btn.exists:
                self.logger.debug("No 'Follow back' buttons found — may not be in non-followers view")
                return results

            username_elements = d(resourceId=username_resource_id)
            if not username_elements.exists:
                return results

            for i in range(username_elements.count):
                try:
                    username = username_elements[i].get_text() or ''
                    username = username.strip().lstrip('@')
                    if username and self._is_valid_username(username):
                        results.append(username)
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Error extracting non-follower usernames: {e}")

        return results

    def _is_valid_username(self, username: str) -> bool:
        """Vérifier qu'une chaîne est un username Instagram valide."""
        if not username or len(username) < 1 or len(username) > 30:
            return False
        # Exclure les textes qui ne sont pas des usernames
        excluded = {
            'search', 'categories', 'all followers', 'following', 'followers',
            'subscriptions', 'flagged', 'most shown in feed', 'sorted by',
            'date followed', 'default', 'sync contacts', 'find people you know',
            'sync', 'dismiss', 'follow back', 'following', 'new posts',
        }
        if username.lower() in excluded:
            return False
        # Un username Instagram ne contient que des lettres, chiffres, points, underscores
        import re
        return bool(re.match(r'^[a-zA-Z0-9._]+$', username))
