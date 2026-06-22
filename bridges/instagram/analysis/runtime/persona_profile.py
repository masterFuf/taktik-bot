"""Profile navigation helpers for the Instagram Persona Analysis bridge."""

from __future__ import annotations

import time

from bridges.instagram.runtime.ipc import _ipc


class PersonaProfileMixin:
    """Open the target profile and copy profile metadata into the result payload."""

    def open_target_profile(self, collected: dict):
        _ipc.status("navigating_own_profile", "Navigation vers l'onglet profil\u2026")

        from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
        from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness

        nav = NavigationActions(self.device_manager)
        profile_biz = ProfileBusiness(self.device_manager)

        nav.navigate_to_profile_tab()
        time.sleep(2)

        _ipc.status("detecting_account", "D\u00e9tection du compte connect\u00e9\u2026")
        # enrich=False: the "About this account" enrichment clicks the username header, which
        # opens the account-switcher popup and pollutes the persona screenshot. We only copy
        # basic fields (name/bio/website/counts) below, none of which need enrichment.
        own_info = profile_biz.get_complete_profile_info(navigate_if_needed=False, enrich=False)
        own_username = (own_info.get("username") or "").lower() if own_info else ""

        if own_username == self.target_username:
            _ipc.status(
                "own_profile_detected",
                f"Compte @{self.target_username} connect\u00e9 \u2014 profil propre utilis\u00e9",
            )
            self._copy_profile_info(own_info, collected)
            return nav, None

        _ipc.status(
            "navigating_public_profile",
            (
                f"Compte diff\u00e9rent ({own_username or 'inconnu'}), "
                f"navigation vers @{self.target_username}\u2026"
            ),
        )
        ok = nav.navigate_to_profile(self.target_username)
        if not ok:
            _ipc.error(f"Impossible d'acc\u00e9der au profil @{self.target_username}")
            return None, {"success": False, "error": f"Cannot navigate to @{self.target_username}"}

        time.sleep(2)
        # enrich=False: avoid the username-header click that opens the account switcher (see above).
        profile_info = profile_biz.get_complete_profile_info(navigate_if_needed=False, enrich=False)
        self._copy_profile_info(profile_info, collected)
        return nav, None

    def _copy_profile_info(self, profile_info, collected: dict) -> None:
        if not profile_info:
            return

        collected["full_name"] = profile_info.get("full_name")
        collected["biography"] = profile_info.get("biography")
        collected["website"] = profile_info.get("website")
        collected["followers_count"] = profile_info.get("followers_count")
        collected["following_count"] = profile_info.get("following_count")
        collected["posts_count"] = profile_info.get("posts_count")
