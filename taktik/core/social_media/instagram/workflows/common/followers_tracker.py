"""Tracker diagnosing navigation problems in a followers list."""

import json
import os

from taktik.core.shared.app_paths import get_app_data_dir
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


class FollowersTracker:
    """
    Records the movements through the followers list to diagnose:
    - going back to the top of the list (infinite loops)
    - revisiting already-filtered profiles
    - scrolling problems
    """
    
    def __init__(self, account_username: str, target_username: str):
        self.account_username = account_username
        self.target_username = target_username
        self.session_start = datetime.now()
        
        # Create the log directory in the user data folder to avoid permission issues
        app_data = get_app_data_dir()
        self.log_dir = Path(app_data) / 'logs' / 'followers_tracking'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log file for this session
        timestamp = self.session_start.strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{account_username}_{target_username}_{timestamp}.jsonl"
        
        # Internal state used to detect anomalies
        self.visited_usernames: List[str] = []  # Ordre de visite
        self.visible_history: List[List[str]] = []  # history of the visible pages
        # Scroll counter at the time of each entry of `visible_history`, same length and same
        # order. It is what tells "I looked five times" from "I scrolled five times" — see
        # `_pages_settled_after_each_scroll`.
        self.visible_history_scrolls: List[int] = []
        self.scroll_count = 0
        self.loop_detected_count = 0
        self.repeats_to_end = 5  # identical pages needed to call the end
        self.first_page_usernames: List[str] = []  # first page seen, to detect a jump back to the top
        
        # Écrire l'en-tête de session
        self._log_event("session_start", {
            "account": account_username,
            "target": target_username,
            "timestamp": self.session_start.isoformat()
        })
    
    def _log_event(self, event_type: str, data: Dict[str, Any]):
        """Write one event to the log file."""
        entry = {
            "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "elapsed_s": (datetime.now() - self.session_start).total_seconds(),
            "event": event_type,
            **data
        }
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    def log_visible_followers(self, visible_usernames: List[str], after_action: str = "scan"):
        """
        Record the followers visible on screen.
        Detects whether we came back to the top of the list.

        Returns:
            bool: True when a loop back to the top is detected
        """
        # Store the first page for reference
        if not self.first_page_usernames and visible_usernames:
            self.first_page_usernames = visible_usernames.copy()
        
        self.visible_history.append(visible_usernames.copy())
        self.visible_history_scrolls.append(self.scroll_count)

        # === DÉTECTION DE BOUCLE (style Insomniac) ===
        loop_detected = False
        is_same_as_previous = False
        consecutive_same_pages = 0
        
        if len(self.visible_history) >= 2:
        # Is the current page identical to the previous one?
            prev_page = self.visible_history[-2]
            is_same_as_previous = visible_usernames == prev_page
            
        # Count consecutive identical pages
            if is_same_as_previous:
                for i in range(len(self.visible_history) - 1, 0, -1):
                    if self.visible_history[i] == self.visible_history[i-1]:
                        consecutive_same_pages += 1
                    else:
                        break
        
        # Detect a jump back to the top of the list
        if len(self.visible_history) > 5 and visible_usernames and self.first_page_usernames:
        # Compare with the first page
                # At least two of the first three usernames identical -> back to the top
            common_with_first = sum(1 for a, b in zip(visible_usernames[:3], self.first_page_usernames[:3]) if a == b)
            if common_with_first >= 2:
                loop_detected = True
                self.loop_detected_count += 1
        
        self._log_event("visible_followers", {
            "action": after_action,
            "count": len(visible_usernames),
            "usernames": visible_usernames[:10],  # capped for readability
            "scroll_count": self.scroll_count,
            "loop_detected": loop_detected,
            "is_same_as_previous": is_same_as_previous,
            "consecutive_same_pages": consecutive_same_pages,
            "history_size": len(self.visible_history)
        })
        
        if loop_detected:
            self._log_event("WARNING_LOOP_DETECTED", {
                "message": "Retour en début de liste détecté!",
                "first_page": self.first_page_usernames[:5],
                "current_page": visible_usernames[:5],
                "total_loops": self.loop_detected_count
            })
        
        return loop_detected
    
    def _pages_settled_after_each_scroll(self) -> List[List[str]]:
        """One page per scroll: the LAST state seen while the list had not moved again.

        `visible_history` is fed on EVERY scan, and the loop deliberately rescans the same page
        while it still holds a fresh follower (process one -> back -> rescan). So the history
        naturally contains runs of identical pages that no scroll separates: reading it raw
        answers "did I look at the same page N times", which is always true on a page being
        worked through, instead of "did N scrolls fail to bring anything new".

        Collapsing on the scroll counter restores the intended question. Same split as the
        `new_usernames_found == 0` gate that protects `ScrollEndDetector` in the direct loop —
        this tracker was simply never given it.
        """
        pages: List[List[str]] = []
        last_scroll: Optional[int] = None
        for page, scrolls in zip(self.visible_history, self.visible_history_scrolls):
            if pages and scrolls == last_scroll:
                pages[-1] = page  # same scroll: the later reading is the settled one
            else:
                pages.append(page)
                last_scroll = scrolls
        return pages

    def is_end_of_list(self) -> bool:
        """
        Detect whether the end of the list is reached.

        Conditions guarding against false positives:
        - a minimum number of scrolls performed
        - a minimum number of usernames seen
        - the last N pages, one per scroll, are identical
        """
        # Avoid false positives at the very start of a session
        if self.scroll_count < 10:
            return False

        # Count the unique usernames seen in the history
        all_seen_usernames = set()
        for page in self.visible_history:
            all_seen_usernames.update(page)

        if len(all_seen_usernames) < 50:
            return False

        # One page per scroll, never one per look: five rescans of a page the loop is still
        # working through are not five scrolls that brought nothing.
        pages = self._pages_settled_after_each_scroll()

        if len(pages) < self.repeats_to_end:
            return False

        last_page = pages[-1]
        for i in range(2, self.repeats_to_end + 1):
            if pages[-i] != last_page:
                return False

        self._log_event("END_OF_LIST_DETECTED", {
            "message": f"Mêmes followers vus après {self.repeats_to_end} scrolls consécutifs "
                       f"(total {self.scroll_count} scrolls)",
            "last_page": last_page[:5],
            "total_visited": len(self.visited_usernames),
            "scroll_count": self.scroll_count,
            "scans": len(self.visible_history),
            "pages_after_scroll": len(pages),
        })
        return True
    
    def check_position_after_back(self, expected_username: str, visible_usernames: List[str]) -> bool:
        """
        Check we came back to the right position after a back().

        Args:
            visible_usernames: usernames currently visible

        Returns:
            bool: True when the position is correct
        """
        position_ok = expected_username in visible_usernames
        
        self._log_event("position_check_after_back", {
            "expected": expected_username,
            "found": position_ok,
            "visible_sample": visible_usernames[:5]
        })
        
        if not position_ok:
            self._log_event("WARNING_POSITION_LOST", {
                "message": f"Position perdue! @{expected_username} n'est plus visible",
                "visible": visible_usernames[:5]
            })
        
        return position_ok
    
    def log_scroll(self, direction: str = "down"):
        """Enregistre un scroll."""
        self.scroll_count += 1
        self._log_event("scroll", {
            "direction": direction,
            "scroll_number": self.scroll_count
        })
    
    def log_profile_visit(self, username: str, position_in_list: int, 
                          already_in_db: bool = False, filter_reason: Optional[str] = None):
        """
        Record a profile visit.
        """
        is_revisit = username in self.visited_usernames
        visit_number = self.visited_usernames.count(username) + 1
        
        self.visited_usernames.append(username)
        
        self._log_event("profile_visit", {
            "username": username,
            "position": position_in_list,
            "visit_number": visit_number,
            "is_revisit": is_revisit,
            "already_in_db": already_in_db,
            "total_visited": len(set(self.visited_usernames))
        })
        
        if is_revisit:
            self._log_event("WARNING_REVISIT", {
                "message": f"Profil @{username} déjà visité cette session!",
                "previous_visits": visit_number - 1
            })
    
    def log_profile_filtered(self, username: str, reason: str, profile_data: Dict[str, Any]):
        """Record a filtered profile with its data."""
        self._log_event("profile_filtered", {
            "username": username,
            "reason": reason,
            "posts": profile_data.get("posts_count", 0),
            "followers": profile_data.get("followers_count", 0),
            "following": profile_data.get("following_count", 0),
            "is_private": profile_data.get("is_private", False)
        })
    
    def log_profile_interacted(self, username: str, actions: Dict[str, bool]):
        """Record a successful interaction."""
        self._log_event("profile_interacted", {
            "username": username,
            "liked": actions.get("liked", False),
            "followed": actions.get("followed", False),
            "story_viewed": actions.get("story_viewed", False),
            "commented": actions.get("commented", False)
        })
    
    def log_skipped_from_db(self, username: str, reason: str):
        """Record a profile skipped because already in the database."""
        self._log_event("skipped_from_db", {
            "username": username,
            "reason": reason
        })
    
    def log_recovery_attempt(self, reason: str, success: bool):
        """Record a navigation recovery attempt."""
        self._log_event("recovery_attempt", {
            "reason": reason,
            "success": success
        })
    
    def log_position_check(self, last_visited: str, next_expected: str, 
                           visible_usernames: List[str], position_ok: bool):
        """Record a position check after coming back from a profile."""
        self._log_event("position_check", {
            "last_visited": last_visited,
            "next_expected": next_expected,
            "visible_sample": visible_usernames[:5],
            "position_ok": position_ok
        })
    
    def log_session_end(self, stats: Dict[str, Any]):
        """Record the end of the session, with its statistics."""
        self._log_event("session_end", {
            "duration_s": (datetime.now() - self.session_start).total_seconds(),
            "total_scrolls": self.scroll_count,
            "unique_visited": len(set(self.visited_usernames)),
            "total_visits": len(self.visited_usernames),
            "loops_detected": self.loop_detected_count,
            "stats": stats
        })
        
        # Emit a summary when problems were detected
        if self.loop_detected_count > 0:
            self._log_event("SUMMARY_ISSUES", {
                "loops_detected": self.loop_detected_count,
                "message": "Des boucles ont été détectées - vérifier les logs pour plus de détails"
            })
    
    def get_log_file_path(self) -> str:
        """Path of the log file."""
        return str(self.log_file)
