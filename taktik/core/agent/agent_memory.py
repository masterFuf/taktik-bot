"""Chronological memory reconstruction for the autonomous Taktik Agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger


class AgentMemory:
    """Build a compact ordered timeline from existing SQLite tables.

    V1 intentionally does not add a new table. It reconstructs useful episodes
    from sessions, scraping sessions, and interaction_history so the planner can
    avoid repeating the same sequence every day.
    """

    def __init__(self, db_service: Any):
        self.db = db_service

    def load_recent_timeline(
        self,
        account_id: Optional[int],
        account_username: str = "",
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        """Return recent automation/scraping episodes ordered oldest -> newest."""
        if not account_id:
            return []

        episodes: List[Dict[str, Any]] = []
        episodes.extend(self._load_automation_sessions(account_id, limit=limit))
        episodes.extend(self._load_scraping_sessions(account_id, limit=limit))

        episodes.sort(key=lambda item: item.get("started_at") or "")
        return episodes[-limit:]

    def build_pattern_warnings(self, timeline: List[Dict[str, Any]]) -> List[str]:
        """Detect simple repetition signals from the ordered timeline."""
        warnings: List[str] = []
        if len(timeline) < 2:
            return warnings

        last = timeline[-1]
        previous = timeline[-2]
        last_tool = last.get("tool")
        previous_tool = previous.get("tool")

        if last_tool and previous_tool and last_tool == previous_tool:
            warnings.append(f"The last two useful episodes both used {last_tool}.")

        recent_tools = [episode.get("tool") for episode in timeline[-4:] if episode.get("tool")]
        if recent_tools and "read_dm_inbox" not in recent_tools:
            warnings.append("DM inbox was not checked in the recent timeline.")

        if recent_tools.count("explore_hashtag") >= 2:
            warnings.append("Hashtag exploration appeared multiple times recently.")

        if recent_tools.count("browse_feed") >= 3:
            warnings.append("Feed browsing dominated the recent timeline.")

        return warnings

    def summarize_timeline(self, timeline: List[Dict[str, Any]], max_episodes: int = 4) -> str:
        """Human-readable compact summary for prompts and narration."""
        if not timeline:
            return "No recent automation timeline found for this account."

        lines: List[str] = []
        for episode in timeline[-max_episodes:]:
            started = _human_time(episode.get("started_at"))
            tool = episode.get("tool") or episode.get("workflow_type") or "unknown"
            sequence = " -> ".join(episode.get("sequence", [])[:6]) or "no recorded actions"
            outcome = episode.get("outcome", {})
            outcome_text = _format_outcome(outcome)
            lines.append(f"- {started}: {tool}; sequence: {sequence}; outcome: {outcome_text}")
        return "\n".join(lines)

    def _load_automation_sessions(self, account_id: int, limit: int) -> List[Dict[str, Any]]:
        episodes: List[Dict[str, Any]] = []
        try:
            sessions = self.db.get_sessions_by_account(account_id, limit=limit)
        except Exception as exc:
            logger.debug(f"[AgentMemory] Could not load automation sessions: {exc}")
            return episodes

        for session in sessions:
            session_id = session.get("session_id")
            interactions = self._load_interactions_for_session(session_id)
            sequence = _compress_sequence(
                [str(item.get("interaction_type") or item.get("type") or "").lower() for item in interactions]
            )
            outcome = self._count_interactions(interactions)

            episodes.append({
                "episode_id": f"session:{session_id}",
                "platform": "instagram",
                "account_id": account_id,
                "session_id": session_id,
                "started_at": session.get("start_time") or session.get("created_at"),
                "ended_at": session.get("end_time"),
                "workflow_type": session.get("target_type") or "automation",
                "tool": _map_session_tool(session),
                "target": session.get("target"),
                "status": session.get("status"),
                "duration_seconds": session.get("duration_seconds") or 0,
                "sequence": sequence,
                "actions": interactions[:30],
                "outcome": outcome,
            })
        return episodes

    def _load_scraping_sessions(self, account_id: int, limit: int) -> List[Dict[str, Any]]:
        episodes: List[Dict[str, Any]] = []
        try:
            sessions = self.db.get_scraping_sessions(limit=limit * 2)
        except Exception as exc:
            logger.debug(f"[AgentMemory] Could not load scraping sessions: {exc}")
            return episodes

        matching_sessions = [session for session in sessions if session.get("account_id") == account_id]
        if not matching_sessions:
            # Older scraping rows may not be linked to an account. Use them only
            # as a fallback so account-specific history stays clean when present.
            matching_sessions = [session for session in sessions if session.get("account_id") is None]

        for session in matching_sessions:

            scraping_id = session.get("scraping_id")
            episodes.append({
                "episode_id": f"scraping:{scraping_id}",
                "platform": session.get("platform") or "instagram",
                "account_id": session.get("account_id"),
                "scraping_id": scraping_id,
                "started_at": session.get("start_time") or session.get("created_at"),
                "ended_at": session.get("end_time"),
                "workflow_type": "scraping",
                "tool": _map_scraping_tool(session),
                "target": session.get("source_name"),
                "status": session.get("status"),
                "duration_seconds": session.get("duration_seconds") or 0,
                "sequence": [
                    f"scrape_{session.get('source_type') or 'source'}",
                    f"collect_{session.get('scraping_type') or 'profiles'}",
                ],
                "actions": [],
                "outcome": {
                    "profiles_scraped": session.get("total_scraped") or 0,
                    "errors": 1 if str(session.get("status")).upper() in ("ERROR", "FAILED") else 0,
                },
            })

            if len(episodes) >= limit:
                break
        return episodes

    def _load_interactions_for_session(self, session_id: Optional[int]) -> List[Dict[str, Any]]:
        if not session_id:
            return []
        try:
            interactions = self.db.interactions.find_by_session(session_id)
        except Exception as exc:
            logger.debug(f"[AgentMemory] Could not load interactions for session {session_id}: {exc}")
            return []

        interactions.sort(key=lambda item: item.get("interaction_time") or "")
        return [
            {
                "at": item.get("interaction_time"),
                "type": item.get("interaction_type"),
                "target": item.get("target_username"),
                "result": "ok" if item.get("success") else "failed",
                "content": item.get("content"),
            }
            for item in interactions
        ]

    @staticmethod
    def _count_interactions(interactions: List[Dict[str, Any]]) -> Dict[str, int]:
        counts = {
            "likes": 0,
            "comments": 0,
            "follows": 0,
            "unfollows": 0,
            "story_views": 0,
            "story_likes": 0,
            "story_reactions": 0,
            "dm_replies": 0,
            "errors": 0,
        }
        for item in interactions:
            action = str(item.get("interaction_type") or item.get("type") or "").upper()
            if not item.get("success", True):
                counts["errors"] += 1
            if action == "LIKE":
                counts["likes"] += 1
            elif action == "COMMENT":
                counts["comments"] += 1
            elif action == "FOLLOW":
                counts["follows"] += 1
            elif action == "UNFOLLOW":
                counts["unfollows"] += 1
            elif action == "STORY_WATCH":
                counts["story_views"] += 1
            elif action == "STORY_LIKE":
                counts["story_likes"] += 1
            elif action == "STORY_REACTION":
                counts["story_reactions"] += 1
            elif action in ("DM_REPLY", "DM_SENT"):
                counts["dm_replies"] += 1
        return counts


def _map_session_tool(session: Dict[str, Any]) -> str:
    target_type = str(session.get("target_type") or "").lower()
    session_name = str(session.get("session_name") or "").lower()
    if "hashtag" in target_type or "hashtag" in session_name:
        return "explore_hashtag"
    if "dm" in target_type or "dm" in session_name:
        return "read_dm_inbox"
    if "feed" in target_type or "feed" in session_name:
        return "browse_feed"
    if "taktik" in session_name or "agent" in session_name:
        return "agent_session"
    return target_type or "automation"


def _map_scraping_tool(session: Dict[str, Any]) -> str:
    scraping_type = str(session.get("scraping_type") or "").lower()
    source_type = str(session.get("source_type") or "").lower()
    if "deep" in scraping_type:
        return "deep_qualify_profile"
    if source_type == "hashtag":
        return "scrape_hashtag"
    if source_type in ("target", "profile"):
        return "scrape_target"
    return "scraping"


def _compress_sequence(actions: List[str]) -> List[str]:
    result: List[str] = []
    previous = None
    count = 0
    for action in [a for a in actions if a]:
        if action == previous:
            count += 1
            continue
        if previous:
            result.append(f"{previous} x{count}" if count > 1 else previous)
        previous = action
        count = 1
    if previous:
        result.append(f"{previous} x{count}" if count > 1 else previous)
    return result


def _format_outcome(outcome: Dict[str, Any]) -> str:
    parts = [f"{key}={value}" for key, value in outcome.items() if value]
    return ", ".join(parts) if parts else "no measurable action"


def _human_time(value: Optional[str]) -> str:
    if not value:
        return "unknown time"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)
