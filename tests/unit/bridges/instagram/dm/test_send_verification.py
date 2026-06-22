"""Unit tests for DM send confirmation.

``send_message`` must only report success once our text is confirmed as the newest
OUTGOING bubble in the thread. A click that does not actually submit (empty composer,
mis-targeted button, IG hiccup) returns False so the caller never persists a phantom
reply that was never delivered (the blissand_glow case: a `sent` row in dm_messages
with no matching message in the real conversation).
"""

from bridges.instagram.engagement.runtime.dm.sender import DMSenderMixin


class _Verifier(DMSenderMixin):
    """Minimal harness exposing the matcher over a fixed set of on-screen bubbles."""

    def __init__(self, bubbles):
        self._bubbles = bubbles

    def _collect_text_messages(self):
        return self._bubbles


def _bubble(text, is_sent, top):
    return {"type": "text", "text": text, "is_sent": is_sent, "top": top}


def test_normalize_collapses_whitespace_and_case():
    assert DMSenderMixin._normalize_message("  Merci   BEAUCOUP\n!  ") == "merci beaucoup !"
    assert DMSenderMixin._normalize_message(None) == ""


def test_confirmed_when_our_message_is_last_outgoing_bubble():
    bubbles = [
        _bubble("Merci de t'être abonnée !", is_sent=False, top=100),
        _bubble("Merci beaucoup pour ton accueil !", is_sent=True, top=300),
    ]
    assert _Verifier(bubbles)._message_appears_as_last_sent("Merci beaucoup pour ton accueil !") is True


def test_not_confirmed_when_last_bubble_is_incoming():
    # Composer never submitted: the newest bubble is still THEIRS.
    bubbles = [_bubble("Merci de t'être abonnée !", is_sent=False, top=100)]
    assert _Verifier(bubbles)._message_appears_as_last_sent("Merci beaucoup pour ton accueil !") is False


def test_not_confirmed_on_empty_thread():
    assert _Verifier([])._message_appears_as_last_sent("anything") is False


def test_no_false_positive_from_an_identical_earlier_outgoing():
    # We sent this exact text before; this send failed, so the LAST bubble is theirs.
    bubbles = [
        _bubble("Coucou !", is_sent=True, top=100),
        _bubble("ça va ?", is_sent=False, top=300),
    ]
    assert _Verifier(bubbles)._message_appears_as_last_sent("Coucou !") is False


def test_long_message_prefix_match_when_ig_elides():
    sent = "Merci beaucoup pour ton accueil ! Pour l'instant je m'intéresse au breathwork."
    shown = "Merci beaucoup pour ton accueil ! Pour l'instant je m'intéresse"  # elided
    bubbles = [_bubble(shown, is_sent=True, top=200)]
    assert _Verifier(bubbles)._message_appears_as_last_sent(sent) is True


def test_short_message_requires_exact_match():
    bubbles = [_bubble("ok", is_sent=True, top=200)]
    assert _Verifier(bubbles)._message_appears_as_last_sent("ok") is True
    # A short prefix must NOT loosely match a different short bubble.
    bubbles = [_bubble("oui", is_sent=True, top=200)]
    assert _Verifier(bubbles)._message_appears_as_last_sent("ok") is False


def test_verify_returns_false_without_retrying_forever():
    # attempts=1 → no sleep; confirms the polling wrapper honours the matcher.
    assert _Verifier([])._verify_message_sent("x", attempts=1) is False
