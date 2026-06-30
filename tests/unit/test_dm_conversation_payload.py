"""Unit tests for the Instagram DM early-exit helpers (no device / no real DB needed for the
pure matcher; a temp SQLite connection covers the thread last-message lookup)."""

from bridges.instagram.engagement.runtime.dm.conversation_payload import (
    build_up_to_date_conversation,
    inbox_preview_matches_known,
)
from taktik.core.database.repositories.messaging.dm_thread_repository import DmThreadRepository


class TestInboxPreviewMatchesKnown:
    def test_full_message_visible_in_row_matches(self):
        # Non-truncated row: the stored last message appears verbatim in the inbox digest.
        content_desc = "fabrice, Trop cool ! Content que ca roule pour toi aussi, 11:27"
        assert inbox_preview_matches_known(
            content_desc, "fabrice", "Trop cool ! Content que ca roule pour toi aussi"
        )

    def test_truncated_preview_prefix_matches(self):
        # Truncated row: the visible prefix (before the ellipsis) prefixes the stored message.
        content_desc = "dsnutrition._, Salut ! Merci beaucoup pour ton message et t…, 09:41"
        known = "Salut ! Merci beaucoup pour ton message et toute ta gentillesse"
        assert inbox_preview_matches_known(content_desc, "dsnutrition._", known)

    def test_new_different_message_does_not_match(self):
        content_desc = "alice, Une toute nouvelle question sans rapport, 10:00"
        assert not inbox_preview_matches_known(content_desc, "alice", "Salut ! Comment ca va ?")

    def test_too_short_known_text_never_matches(self):
        # "ok" / a lone emoji is too ambiguous to skip on safely.
        assert not inbox_preview_matches_known("bob, ok, 10:00", "bob", "ok")

    def test_outgoing_digest_row_does_not_match_stored_text(self):
        # When WE sent last, the row shows a "Sent…" digest, not the message — never a match.
        assert not inbox_preview_matches_known(
            "fabrice, Envoye il y a 2 h", "fabrice", "Trop cool ! Content que ca roule"
        )

    def test_empty_inputs_do_not_match(self):
        assert not inbox_preview_matches_known("", "alice", "hello there")
        assert not inbox_preview_matches_known("alice, hello there, 10:00", "alice", "")


class TestBuildUpToDateConversation:
    def test_their_last_message_stays_replyable(self):
        conv = build_up_to_date_conversation(
            real_username="alice", inbox_username="alice", last_is_ours=False
        )
        assert conv["messages"] == []
        assert conv["up_to_date"] is True
        assert conv["last_message_is_ours"] is False
        assert conv["can_reply"] is True

    def test_our_last_message_is_not_replyable(self):
        conv = build_up_to_date_conversation(
            real_username="bob", inbox_username="bob", last_is_ours=True
        )
        assert conv["last_message_is_ours"] is True
        assert conv["can_reply"] is False


class TestFindLastMessage:
    def test_lookup_by_partner_and_external_thread_id(self, conn):
        repo = DmThreadRepository(conn)
        repo.upsert(
            platform="instagram",
            account_id=1,
            partner_username="Alice",
            external_thread_id="alice_inbox",
            last_message_text="Hello there friend",
            last_message_is_ours=False,
        )
        # The reader has the inbox-row username before opening; match it against either the
        # persisted partner handle (lowercased) or the external_thread_id (inbox username).
        assert repo.find_last_message("instagram", 1, "alice") == {
            "text": "Hello there friend",
            "is_ours": False,
        }
        assert repo.find_last_message("instagram", 1, "alice_inbox")["text"] == "Hello there friend"
        assert repo.find_last_message("instagram", 1, "unknown_user") is None
