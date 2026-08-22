"""The terminal status follows the motive — the step the catalogue had left open.

Measured on 25 consecutive production runs before this rule existed: 23 were filed COMPLETED,
including five that ended on `navigation_lost` and one that never opened the followers list and
stopped after 44 seconds with zero interactions. The motive was correct in every log; the status
contradicted it, so nothing downstream — the recap, the sessions page, the analytics — could tell
a finished run from a failed one.
"""

from taktik.core.social_media.instagram.workflows.management.session import stop_reasons


class TestTerminalStatus:
    def test_failed_family_is_interrupted(self):
        """A run that did not run is INTERRUPTED, whatever the caller would have said."""
        for reason in (
            stop_reasons.navigation_lost(),
            stop_reasons.list_unavailable(),
            stop_reasons.empty_plan(),
        ):
            assert stop_reasons.terminal_status(reason) == 'INTERRUPTED', reason

    def test_ok_family_is_completed(self):
        """Reaching a limit, exhausting the sources or finishing the list are NOT failures."""
        for reason in (
            stop_reasons.completed(14),
            stop_reasons.sources_exhausted(),
        ):
            assert stop_reasons.terminal_status(reason) == 'COMPLETED', reason

    def test_bare_legacy_string_still_classifies(self):
        """Some call sites still hand over the plain code; it must not lose its family."""
        assert stop_reasons.terminal_status('navigation_lost') == 'INTERRUPTED'
        assert stop_reasons.terminal_status('list_unavailable') == 'INTERRUPTED'

    def test_unknown_reason_keeps_the_default(self):
        """An undeclared motive must not silently reclassify a run as failed.

        That would be the same mistake as the one this rule fixes, pointing the other way.
        """
        assert stop_reasons.terminal_status('something nobody declared') == 'COMPLETED'
        assert stop_reasons.terminal_status(None) == 'COMPLETED'
        assert stop_reasons.terminal_status('') == 'COMPLETED'
