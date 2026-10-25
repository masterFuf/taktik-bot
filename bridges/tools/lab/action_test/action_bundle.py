"""Shared action bundle container for compat action-test diagnostics."""

from loguru import logger


class LabRunIdentity:
    """What a run hands the production classes it builds as their `automation`: the account their
    work is filed under (in Symfony terms, the security token every service reads).

    A run builds its businesses with itself (`InstagramAutomation`); every one of them asks it for
    the account (`_get_account_id`), and so does every business it builds in turn, such as the
    feed's `like_business`, which records the likes of the likers loop. The Lab bundle builds its
    classes with this one, and `ActionBundle.bind_account` sets it. No `current_session_id` here:
    the session comes from the session manager an action attaches (`_get_session_id` falls back to
    it), as for the suggestions visit.

    `active_username` is the handle of that account, as a run reads it off its own profile: the
    likers loop and the reading of the likers leave it out of the profiles they open.
    """

    def __init__(self) -> None:
        self.active_account_id = None
        self.active_username = None


class ActionBundle:
    """Holds diagnostic action instances grouped by family."""

    def __init__(self) -> None:
        #: Given to the production classes the bundle builds, as a run gives itself.
        self.identity = LabRunIdentity()

    #: Serial of the phone this bundle drives, set by the session or the single-shot runner.
    #: An action that builds its own manager (`app.launch`) must pass it on: a manager without a
    #: serial falls back to the first phone of `adb devices`.
    device_id = None

    #: Components whose work is recorded against an account. Anything the bundle builds
    #: that is not in here writes nothing, so it needs no identity.
    _IDENTITY_BEARING = ("comment", "like", "story", "feed", "unfollow", "popup")

    def bind_account(self, account_id, username=None) -> int:
        """Attach every recording component to ``account_id``, and the run to ``username``, its
        handle. Returns how many components were bound.

        The Lab runs production classes on a real device, so what they write is real. Built
        without an identity, those classes used to file everything under a default account
        id — that is, under someone else's name — and the fix had been applied by hand in
        one action, leaving every other action wrong. Binding happens here now, once per
        action run, for the whole bundle.

        No account means no identity: the components are reset to a null one and their own guard
        refuses to record, which is visible in the log rather than silently wrong. The Lab session
        keeps its bundle from one action to the next: without the reset, an action run without an
        account wrote under the account of the action before it.
        """
        identity = account_id or None
        self.identity.active_account_id = identity
        self.identity.active_username = (username or None) if identity is not None else None
        bound = 0
        for name in self._IDENTITY_BEARING:
            component = getattr(self, name, None)
            if component is not None and hasattr(component, "active_account_id"):
                component.active_account_id = identity
                bound += 1
        if identity is None:
            return 0
        logger.debug(f"Lab bundle bound to account {account_id} ({bound} components)")
        return bound


def attach_device_id(bundle, device_id) -> None:
    """Record on the bundle which phone it drives. Never raises (a test bundle may be a stub)."""
    try:
        bundle.device_id = device_id or None
    except (AttributeError, TypeError):
        pass


def bundle_device_id(bundle):
    """The serial of the phone a bundle drives: the one recorded, else the connected device's own.

    None when neither is known. The caller must then refuse to act rather than let a manager pick
    a phone by itself.
    """
    recorded = getattr(bundle, "device_id", None)
    if recorded:
        return recorded
    device = getattr(bundle, "device", None)
    raw = getattr(device, "_device", None) or device
    serial = getattr(raw, "serial", None)
    return serial if isinstance(serial, str) and serial else None


def open_bot_base() -> None:
    """Open the bot's base, the one `TAKTIK_DB_PATH` names, as every run opens it before its first
    gesture (`configure_run_database` of the bridges); once per process. The production classes the
    Lab drives read and write it (a profile already processed, a like recorded): opened only to
    resolve the `account` parameter, an action run without it logged « Database service not
    configured » and wrote nothing (Pixel 6a, 2026-10-24). Raises when the base does not open."""
    import taktik.core.database as database

    if database.db_service is None:
        database.configure_db_service()


def lab_account_username(params):
    """The handle the ``account`` parameter names (without its ``@``), or None."""
    return (params.get("account") or "").strip().lstrip("@") or None


def resolve_lab_account_id(params):
    """Account id from the ``account`` parameter, or None.

    Without it, everything an action writes is filed under the default id, that is
    under another account.
    """
    account = lab_account_username(params)
    if not account:
        return None
    try:
        from taktik.core.database import get_db_service

        open_bot_base()
        account_id, _ = get_db_service().get_or_create_account(account, is_bot=True)
        return account_id
    except Exception as exc:  # noqa: BLE001 — attribution must never break the action
        logger.warning(f"Lab: could not resolve account @{account}: {exc}")
        return None


__all__ = ["ActionBundle", "LabRunIdentity", "attach_device_id", "bundle_device_id", "open_bot_base",
           "resolve_lab_account_id"]
