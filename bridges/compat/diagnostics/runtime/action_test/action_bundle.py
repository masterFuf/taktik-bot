"""Shared action bundle container for compat action-test diagnostics."""

from loguru import logger


class ActionBundle:
    """Holds diagnostic action instances grouped by family."""

    #: Components whose work is recorded against an account. Anything the bundle builds
    #: that is not in here writes nothing, so it needs no identity.
    _IDENTITY_BEARING = ("comment", "like", "story", "feed", "unfollow", "popup")

    def bind_account(self, account_id) -> int:
        """Attach every recording component to ``account_id``. Returns how many were bound.

        The Lab runs production classes on a real device, so what they write is real. Built
        without an identity, those classes used to file everything under a default account
        id — that is, under someone else's name — and the fix had been applied by hand in
        one action, leaving every other action wrong. Binding happens here now, once per
        action run, for the whole bundle.

        No account means no binding: the components keep a null identity and their own
        guard refuses to record, which is visible in the log rather than silently wrong.
        """
        if not account_id:
            return 0

        bound = 0
        for name in self._IDENTITY_BEARING:
            component = getattr(self, name, None)
            if component is None:
                continue
            if hasattr(component, "active_account_id"):
                component.active_account_id = account_id
                bound += 1
        logger.debug(f"Lab bundle bound to account {account_id} ({bound} components)")
        return bound


def resolve_lab_account_id(params):
    """Account id from the ``account`` parameter, or None.

    Without it, everything an action writes is filed under the default id, that is
    under another account.
    """
    account = (params.get("account") or "").strip().lstrip("@")
    if not account:
        return None
    try:
        from taktik.core.database import configure_db_service, get_db_service

        configure_db_service()
        account_id, _ = get_db_service().get_or_create_account(account, is_bot=True)
        return account_id
    except Exception as exc:  # noqa: BLE001 — attribution must never break the action
        logger.warning(f"Lab: could not resolve account @{account}: {exc}")
        return None


__all__ = ["ActionBundle", "resolve_lab_account_id"]
