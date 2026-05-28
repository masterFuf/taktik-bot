"""Shared stop policy based on consecutive already-known usernames."""

from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_MAX_CONSECUTIVE_KNOWN_USERNAMES = 150


@dataclass(frozen=True)
class KnownProfileDecision:
    """Result returned after observing a username in a scrolling list."""

    username: str
    status: str
    total_observations: int
    unique_usernames_seen: int
    new_usernames_seen: int
    known_usernames_seen: int
    consecutive_known_usernames: int
    max_consecutive_known_usernames: int
    should_stop: bool


@dataclass
class KnownProfilesStopPolicy:
    """Track list progress using usernames, not scroll counts."""

    max_consecutive_known_usernames: int = DEFAULT_MAX_CONSECUTIVE_KNOWN_USERNAMES
    _seen_usernames: set[str] = field(default_factory=set, init=False)
    total_observations: int = 0
    new_usernames_seen: int = 0
    known_usernames_seen: int = 0
    consecutive_known_usernames: int = 0

    def __post_init__(self) -> None:
        try:
            limit = int(self.max_consecutive_known_usernames)
        except (TypeError, ValueError):
            limit = DEFAULT_MAX_CONSECUTIVE_KNOWN_USERNAMES
        self.max_consecutive_known_usernames = max(1, limit)

    def reset(self) -> None:
        self._seen_usernames.clear()
        self.total_observations = 0
        self.new_usernames_seen = 0
        self.known_usernames_seen = 0
        self.consecutive_known_usernames = 0

    def observe(self, username: str | None, *, is_known: bool) -> KnownProfileDecision:
        """Record a username encounter and decide whether the source is exhausted."""
        normalized = normalize_username(username)
        if not normalized:
            return self._decision("", "ignored")

        self.total_observations += 1

        if normalized in self._seen_usernames:
            return self._decision(normalized, "duplicate")

        if is_known:
            self.known_usernames_seen += 1
            self.consecutive_known_usernames += 1
            self._seen_usernames.add(normalized)
            return self._decision(normalized, "known")

        self._seen_usernames.add(normalized)
        self.new_usernames_seen += 1
        self.consecutive_known_usernames = 0
        return self._decision(normalized, "new")

    def _decision(self, username: str, status: str) -> KnownProfileDecision:
        return KnownProfileDecision(
            username=username,
            status=status,
            total_observations=self.total_observations,
            unique_usernames_seen=len(self._seen_usernames),
            new_usernames_seen=self.new_usernames_seen,
            known_usernames_seen=self.known_usernames_seen,
            consecutive_known_usernames=self.consecutive_known_usernames,
            max_consecutive_known_usernames=self.max_consecutive_known_usernames,
            should_stop=self.consecutive_known_usernames >= self.max_consecutive_known_usernames,
        )


def normalize_username(username: str | None) -> str:
    """Normalize usernames before comparing them across UI rows and DB checks."""
    return (username or "").strip().lstrip("@").lower()
