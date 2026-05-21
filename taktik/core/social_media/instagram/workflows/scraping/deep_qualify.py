"""
Deep-qualify mixin for the Scraping workflow.

When ``deep_qualify=True`` is set in the scraping config, after navigating
to a profile page the bot will:

  1. Open the user's **following** list.
  2. Collect up to ``deep_qualify_max_following`` usernames (fast, 1-2 pages,
     no deep scroll — speed matters more than completeness here).
  3. Press back to return to the profile page.
  4. Cross-reference those usernames against the local DB to enrich the
     context with classification data already known about those accounts
     (niche, tags, cities, etc. — everything *except* the score, which is
     profile-specific and not transferable).
  5. Attach everything to ``profile_data`` so the AI vision call can use it.

The AI receives the following extra context in its user_prompt:
  - ``following_sample``   — raw list of up to N usernames
  - ``known_followings``   — list of dicts with already-classified profiles
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class DeepQualifyMixin:
    """Mixin: collect following sample + DB cross-reference for deep qualification."""

    # ------------------------------------------------------------------
    # Public helpers (called from _scrape_list)
    # ------------------------------------------------------------------

    def _deep_qualify_collect(
        self,
        username: str,
        max_following: int = 30,
    ) -> Dict[str, Any]:
        """
        While already on a profile page, open the following list, collect
        up to *max_following* usernames, cross-reference against DB, then
        return to the profile page.

        Returns a dict ready to be merged into ``profile_data``:
            {
                '_following_sample':  ['user1', 'user2', ...],
                '_known_followings':  [{'username': ..., 'niche_category': ..., ...}, ...],
            }
        On any failure (private account, navigation error), returns empty
        dicts so the caller keeps going without deep context.
        """
        result: Dict[str, Any] = {
            '_following_sample': [],
            '_known_followings': [],
        }

        try:
            following_usernames = self._quick_collect_following(max_count=max_following)
            if following_usernames:
                result['_following_sample'] = following_usernames
                result['_known_followings'] = self._get_known_followings(following_usernames)
                self.logger.debug(
                    f"[deep_qualify] @{username}: collected {len(following_usernames)} followings, "
                    f"{len(result['_known_followings'])} already known in DB"
                )
        except Exception as e:
            self.logger.debug(f"[deep_qualify] @{username}: failed to collect followings — {e}")

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _quick_collect_following(self, max_count: int = 30) -> List[str]:
        """
        Open the following list of the current profile page, collect up to
        *max_count* usernames (1–2 pages, no deep scroll), then press back
        to return to the profile page.

        Uses the same detection + scroll infrastructure as followers/likers.
        """
        usernames: List[str] = []

        # 1. Open the following list -------------------------------------------
        nav = getattr(self, 'nav_actions', None)
        if nav is None or not hasattr(nav, 'open_following_list'):
            self.logger.debug("[deep_qualify] nav_actions.open_following_list not available")
            return usernames

        opened = nav.open_following_list()
        if not opened:
            self.logger.debug("[deep_qualify] Could not open following list (private or unavailable)")
            return usernames

        time.sleep(1.2)  # let the list settle

        # 2. Collect usernames — grab 1 visible page, scroll once if needed ----
        det = getattr(self, 'detection_actions', None)
        scr = getattr(self, 'scroll_actions', None)

        seen: set = set()
        pages_fetched = 0
        max_pages = 2  # at most 2 "pages" to keep it fast (~30–60 usernames)

        while len(usernames) < max_count and pages_fetched < max_pages:
            try:
                visible = det.get_visible_followers_with_elements() if det else []
            except Exception as e:
                self.logger.debug(f"[deep_qualify] get_visible_followers_with_elements failed: {e}")
                break

            new_on_page = 0
            for item in visible:
                u = item.get('username', '').strip()
                if not u or u in seen:
                    continue
                seen.add(u)
                usernames.append(u)
                new_on_page += 1
                if len(usernames) >= max_count:
                    break

            pages_fetched += 1

            # Stop scrolling if we have enough or nothing new appeared
            if len(usernames) >= max_count or new_on_page == 0:
                break

            # One gentle scroll to reveal the next batch
            if scr:
                try:
                    scr.scroll_followers_list_down()
                    time.sleep(0.8)
                except Exception:
                    break

        # 3. Back to profile page -----------------------------------------------
        self.device.press("back")
        time.sleep(1.0)

        return usernames[:max_count]

    def _get_known_followings(self, usernames: List[str]) -> List[Dict[str, Any]]:
        """
        Batch-lookup *usernames* in the local DB and return classification data
        for those that are already known (scraped + qualified).

        Returns a list of dicts with keys:
            username, niche_category, niche, tags, cities, profession,
            summary, full_name, is_business, biography
        Everything *except* ai_score (not meaningful cross-profile).
        """
        if not usernames:
            return []

        try:
            from taktik.core.database.local.service import get_local_database
            db = get_local_database()
            raw_profiles = db.get_profiles_by_usernames(usernames)
        except Exception as e:
            self.logger.debug(f"[deep_qualify] DB batch lookup failed: {e}")
            return []

        known: List[Dict[str, Any]] = []
        for p in raw_profiles:
            # Parse niche / tags out of ai_analysis field if stored there
            ai_analysis = p.get('ai_analysis') or ''

            entry: Dict[str, Any] = {
                'username': p.get('username', ''),
                'full_name': p.get('full_name') or '',
                'biography': p.get('biography') or '',
                'is_business': bool(p.get('is_business', False)),
                'niche_category': p.get('niche_category') or '',
                'niche': p.get('niche') or '',
                'tags': p.get('tags') or [],
                'cities': p.get('cities') or '',
                'profession': p.get('profession') or '',
                'summary': p.get('summary') or ai_analysis,
            }

            # Only include entries that carry at least *some* classification value
            if any([entry['niche_category'], entry['niche'], entry['cities'], entry['profession']]):
                known.append(entry)

        return known
