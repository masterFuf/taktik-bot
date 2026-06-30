"""Unit tests for the Instagram DM early-exit helpers (no device / no real DB needed for the
pure matcher; a temp SQLite connection covers the thread last-message lookup)."""

from bridges.instagram.engagement.runtime.dm.conversation_payload import (
    build_up_to_date_conversation,
    has_unseen_incoming,
    inbox_preview_matches_known,
)
from taktik.core.database.repositories.messaging.dm_thread_repository import DmThreadRepository
from taktik.core.database.repositories.messaging.dm_message_repository import DmMessageRepository


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


class TestHasUnseenIncoming:
    def test_no_incoming_at_all_is_not_unseen(self):
        # Whole thread vanished or only our (sent) messages remain visible.
        assert has_unseen_incoming([{"is_sent": True, "text": "Salut"}], ["Bonjour la"]) is False
        assert has_unseen_incoming([], ["Bonjour la"]) is False

    def test_incoming_all_known_is_not_unseen(self):
        msgs = [{"is_sent": False, "text": "Bonjour, merci pour ton abonnement"}]
        assert has_unseen_incoming(msgs, ["Bonjour, merci pour ton abonnement"]) is False

    def test_new_incoming_is_unseen(self):
        msgs = [
            {"is_sent": False, "text": "Bonjour, merci pour ton abonnement"},
            {"is_sent": False, "text": "Tu es toujours la ?"},
        ]
        assert has_unseen_incoming(msgs, ["Bonjour, merci pour ton abonnement"]) is True


class TestThreadAnswerStateDb:
    """The ephemeral scenario: thread re-read sees only the received message, but a sent message
    is still on record. has_sent_message stays True; mark_answered re-asserts the thread flag."""

    def test_ephemeral_answered_thread(self, conn):
        threads = DmThreadRepository(conn)
        msgs = DmMessageRepository(conn)
        sync_id = threads.upsert(
            platform="instagram",
            account_id=1,
            partner_username="dsnutrition._",
            external_thread_id="dsnutrition._",
            last_message_text="Bonjour, merci pour ton abonnement",
            last_message_is_ours=False,  # clobbered by an ephemeral re-read
            message_count=1,
        )
        msgs.add_message(platform="instagram", thread_sync_id=sync_id, direction="received",
                         text="Bonjour, merci pour ton abonnement", seq=0)
        msgs.add_message(platform="instagram", thread_sync_id=sync_id, direction="sent",
                         text="Salut, merci a toi", seq=1)

        assert threads.find_sync_id_for_inbox("instagram", 1, "dsnutrition._") == sync_id
        # We DID answer (a sent message is on record), even though the thread flag says otherwise.
        assert msgs.has_sent_message("instagram", sync_id) is True
        assert msgs.received_texts("instagram", sync_id) == ["Bonjour, merci pour ton abonnement"]

        # Re-read sees only the received message -> not unseen -> stays answered.
        visible = [{"is_sent": False, "text": "Bonjour, merci pour ton abonnement"}]
        assert has_unseen_incoming(visible, msgs.received_texts("instagram", sync_id)) is False

        # mark_answered re-asserts the (clobbered) thread flag.
        assert threads.mark_answered("instagram", 1, "dsnutrition._") is True
        row = conn.execute(
            "SELECT last_message_is_ours, can_reply FROM dm_threads WHERE sync_id = ?", (sync_id,)
        ).fetchone()
        assert row["last_message_is_ours"] == 1
        assert row["can_reply"] == 0

    def test_thread_without_sent_message(self, conn):
        threads = DmThreadRepository(conn)
        msgs = DmMessageRepository(conn)
        sync_id = threads.upsert(
            platform="instagram", account_id=1, partner_username="newperson",
            external_thread_id="newperson", last_message_text="Coucou ca va",
            last_message_is_ours=False, message_count=1,
        )
        msgs.add_message(platform="instagram", thread_sync_id=sync_id, direction="received",
                         text="Coucou ca va", seq=0)
        # Never answered -> no override should ever fire for this thread.
        assert msgs.has_sent_message("instagram", sync_id) is False
