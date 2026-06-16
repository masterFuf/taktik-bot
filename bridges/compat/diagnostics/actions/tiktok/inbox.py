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
