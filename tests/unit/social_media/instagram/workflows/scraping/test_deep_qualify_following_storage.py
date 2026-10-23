"""What deep qualify does when the base refuses the following list it read, or its classification.

The scraping goes on in every case (the step never interrupts the flow), but each loss is said
at warning level with its size and its cause, not as a debug line nobody reads:

- the following list of a profile that could not be saved (the edges feed the seed lists);
- the accounts awaiting a classification that could not be read: nothing is sent to the AI,
  since an unread pending list is not an empty one and the call is paid for;
- the AI verdicts that could not be saved.
"""

import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from taktik.core.social_media.instagram.workflows.scraping.deep_qualify import DeepQualifyMixin


class _Recorder:
    def __init__(self) -> None:
        self.lines: List[tuple] = []

    def __getattr__(self, level: str):
        return lambda message, *args, **kwargs: self.lines.append((level, message))

    def warnings(self) -> List[str]:
        return [message for level, message in self.lines if level == "warning"]


class _Base:
    """A base that refuses what the test names, and records what it was asked."""

    def __init__(self, refuse: Tuple[str, ...] = ()) -> None:
        self.refuse = refuse
        self.saved_edges: Optional[List[str]] = None

    def get_or_create_profile(self, data: Dict[str, Any]) -> Tuple[int, bool]:
        return 7, False

    def save_profile_followings(self, profile_username: str, following_usernames: List[str],
                                session_id: Optional[str] = None,
                                profile_id: Optional[int] = None) -> int:
        if "edges" in self.refuse:
            raise sqlite3.OperationalError("database is locked")
        self.saved_edges = list(following_usernames)
        return len(following_usernames)

    def get_unclassified_following_usernames(self, limit: int = 200) -> List[str]:
        if "pending" in self.refuse:
            raise sqlite3.OperationalError("no such table: profile_following")
        return ["b1", "b2"]

    def save_following_classifications(self, classifications: Dict[str, Dict[str, str]]) -> int:
        if "classifications" in self.refuse:
            raise sqlite3.OperationalError("database is locked")
        return len(classifications)


class _Ai:
    def __init__(self) -> None:
        self.asked: List[List[str]] = []

    def classify_following_usernames_batch(self, usernames: List[str]) -> Dict[str, Any]:
        self.asked.append(list(usernames))
        return {u: {"niche_category": "sport"} for u in usernames}


class _Workflow(DeepQualifyMixin):
    def __init__(self, base: _Base) -> None:
        self.logger = _Recorder()
        self._ai_service = _Ai()
        self._base = base

    def _local_db(self):
        return self._base


def test_classifications_the_base_refuses_are_said_with_their_count():
    workflow = _Workflow(_Base(refuse=("classifications",)))

    workflow._classify_new_followings(["b1", "b2"])

    warnings = workflow.logger.warnings()
    assert len(warnings) == 1, workflow.logger.lines
    assert "2" in warnings[0] and "database is locked" in warnings[0]


def test_a_following_list_the_base_refuses_is_said_with_its_size():
    workflow = _Workflow(_Base(refuse=("edges",)))

    workflow._save_followings_to_db("alice", ["b1", "b2", "b3"])

    warnings = workflow.logger.warnings()
    assert len(warnings) == 1, workflow.logger.lines
    assert "@alice" in warnings[0] and "3" in warnings[0] and "database is locked" in warnings[0]
    assert not any("new following edge" in message for _, message in workflow.logger.lines), (
        "a refused list must not be traced as saved"
    )


def test_a_saved_following_list_says_nothing_at_warning_level():
    base = _Base()
    workflow = _Workflow(base)

    workflow._save_followings_to_db("alice", ["b1", "b2"])

    assert base.saved_edges == ["b1", "b2"]
    assert workflow.logger.warnings() == []


def test_an_unread_pending_list_sends_nothing_to_the_ai_and_says_it():
    workflow = _Workflow(_Base(refuse=("pending",)))

    workflow._classify_new_followings(["b1", "b2"])

    assert workflow._ai_service.asked == [], "an unread pending list is not an empty one"
    warnings = workflow.logger.warnings()
    assert len(warnings) == 1, workflow.logger.lines
    assert "2" in warnings[0] and "no such table" in warnings[0]


def test_the_pending_accounts_of_the_list_go_to_the_ai():
    workflow = _Workflow(_Base())

    workflow._classify_new_followings(["b1", "b2", "already_done"])

    assert workflow._ai_service.asked == [["b1", "b2"]]
    assert workflow.logger.warnings() == []
