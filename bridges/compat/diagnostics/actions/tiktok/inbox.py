"""Inbox / nouveaux followers actions for TikTok compat diagnostics (inbox v2).

Expose les actions atomiques de la page « Nouveaux followers » pour l'action-test du Lab
(et donc les scénarios). S'appuie sur DMActions (bundle.dm).
"""

from bridges.compat.diagnostics.actions.tiktok import action


@action("tt.inbox.open_new_followers")
def open_new_followers(a, p):
    return a.dm.open_new_followers_page()


@action("tt.inbox.get_new_followers")
def get_new_followers(a, p):
    return a.dm.get_new_followers(int(p.get("max_items", 50)))


@action("tt.inbox.follow_back")
def follow_back(a, p):
    return a.dm.follow_back(p.get("username", ""))


@action("tt.inbox.get_unreplied")
def get_unreplied(a, p):
    """Liste les conversations + indice non-répondu (phase 2)."""
    return a.dm.get_inbox_conversations(int(p.get("max_items", 30)))


@action("tt.inbox.open_message_requests")
def open_message_requests(a, p):
    """Ouvre la page « Demandes de messages » (phase 3)."""
    return a.dm.open_message_requests_page()


@action("tt.inbox.get_requests")
def get_requests(a, p):
    """Liste les demandes de messages (phase 3)."""
    return a.dm.get_message_requests(int(p.get("max_items", 30)))


@action("tt.inbox.open_request")
def open_request(a, p):
    """Ouvre la demande du username donné (phase 3)."""
    return a.dm.open_request(p.get("username", ""))


@action("tt.inbox.accept_request")
def accept_request(a, p):
    """Accepte la demande ouverte (c6b)."""
    return a.dm.accept_request()


@action("tt.inbox.decline_request")
def decline_request(a, p):
    """Refuse/supprime la demande ouverte (c8q)."""
    return a.dm.decline_request()
