"""User-facing narration for the autonomous Taktik Agent."""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from taktik.core.agent.agent_context import AgentContext


class AgentNarrator:
    """Send concise, useful agent narration through IPC."""

    GREETINGS = [
        "Bonjour, je reprends le compte @{username}.",
        "On repart sur @{username}. Je relis le contexte avant d'agir.",
        "Je suis pret pour @{username}. Je commence par regarder l'historique recent.",
    ]

    def __init__(self, ipc=None):
        self.ipc = ipc

    def session_intro(self, context: AgentContext, memory_summary: str) -> None:
        """Explain the account context and recent timeline at session start."""
        username = context.account_username or "unknown"
        greeting = random.choice(self.GREETINGS).format(username=username)
        self.say("intro", greeting, stats={"username": username})

        if memory_summary:
            self.say("memory", memory_summary, stats={
                "timeline_count": len(context.recent_timeline),
                "pattern_warnings": context.pattern_warnings,
            })

        if context.pattern_warnings:
            warning_text = " ".join(context.pattern_warnings[:2])
            self.say("pattern_warning", f"Je vais eviter de repeter les derniers patterns. {warning_text}")

    def next_step(self, message: str, tool: Optional[str] = None, stats: Optional[Dict[str, Any]] = None) -> None:
        """Announce the next high-level action."""
        payload = dict(stats or {})
        if tool:
            payload["tool"] = tool
        self.say("planning", message, stats=payload or None)

    def final_summary(self, stats: Dict[str, Any]) -> None:
        """Summarize the session using live stats."""
        parts: List[str] = []
        if stats.get("likes"):
            parts.append(f"{stats['likes']} likes")
        if stats.get("comments"):
            parts.append(f"{stats['comments']} commentaires")
        if stats.get("follows"):
            parts.append(f"{stats['follows']} follows")
        if stats.get("profile_visits"):
            parts.append(f"{stats['profile_visits']} profils visites")
        if stats.get("posts_seen"):
            parts.append(f"{stats['posts_seen']} posts parcourus")

        summary = ", ".join(parts) if parts else "aucune action mesurable"
        self.say("summary", f"Session terminee : {summary}.", stats=stats)

    def say(self, status: str, message: str, stats: Optional[Dict[str, Any]] = None) -> None:
        """Send a narration message without crashing the workflow on IPC failure."""
        if not self.ipc:
            return
        try:
            self.ipc.agent_status(status=status, message=message, stats=stats)
        except Exception:
            pass
