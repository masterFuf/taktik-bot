"""What deep qualify does when the classifications it paid for cannot be stored.

The AI verdicts on a following list cost a call. When the base refuses them, the scraping
goes on (the step is fire-and-forget), but the loss is said at warning level with its size,
not as a debug line nobody reads.
"""

import sqlite3
from typing import Any, Dict, List

from taktik.core.social_media.instagram.workflows.scraping.deep_qualify import DeepQualifyMixin


class _Recorder:
    def __init__(self) -> None:
        self.lines: List[tuple] = []

    def __getattr__(self, level: str):
        return lambda message, *args, **kwargs: self.lines.append((level, message))


class _RefusingBase:
    def get_unclassified_following_usernames(self, limit: int = 200) -> List[str]:
        return ["b1", "b2"]

    def save_following_classifications(self, classifications: Dict[str, Dict[str, str]]) -> int:
        raise sqlite3.OperationalError("database is locked")


class _Ai:
    def classify_following_usernames_batch(self, usernames: List[str]) -> Dict[str, Any]:
        return {u: {"niche_category": "sport"} for u in usernames}


class _Workflow(DeepQualifyMixin):
    def __init__(self) -> None:
        self.logger = _Recorder()
        self._ai_service = _Ai()

    def _local_db(self):
        return _RefusingBase()


def test_classifications_the_base_refuses_are_said_with_their_count():
    workflow = _Workflow()

    workflow._classify_new_followings(["b1", "b2"])

    warnings = [message for level, message in workflow.logger.lines if level == "warning"]
    assert len(warnings) == 1, workflow.logger.lines
    assert "2" in warnings[0] and "database is locked" in warnings[0]
