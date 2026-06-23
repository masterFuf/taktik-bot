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


@action("tt.inbox.get_notifications")
def get_notifications(a, p):
    """Lit les sections Activité / Notifications système (phase 4, lecture seule)."""
    return a.dm.get_inbox_notifications(int(p.get("max_items", 20)))


@action("tt.inbox.open_conversation")
def open_conversation(a, p):
    """Ouvre la conversation de ``name`` (gateway lecture/réponse DM). Param: name (requis)."""
    name = (p.get("name") or p.get("username") or "").strip()
    if not name:
        return {"success": False, "message": "name param is required"}
    ok = a.dm.click_conversation(name)
    return {"success": bool(ok), "message": f"conversation '{name}' open={ok}"}


@action("tt.inbox.get_messages")
def get_messages(a, p):
    """Lit les messages du fil ouvert (base de l'intelligence de réponse DM). Param: limit
    (défaut 20). Les corps de message ne sont PAS journalisés."""
    msgs = a.dm.get_messages(int(p.get("limit") or 20)) or []
    return {"success": bool(msgs), "count": len(msgs), "messages": msgs,
            "message": f"{len(msgs)} message(s)"}


@action("tt.inbox.send_message")
def send_message(a, p):
    """Envoie un message texte dans le fil ouvert (write d'engagement : tape + send/Enter
    fallback). Param: text (requis)."""
    text = (p.get("text") or "").strip()
    if not text:
        return {"success": False, "message": "text param is required"}
    ok = a.dm.send_text_message(text)
    return {"success": bool(ok), "message": f"message sent={ok}"}
