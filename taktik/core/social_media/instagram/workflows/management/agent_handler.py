"""The one launcher of the Instagram account workflows, and their Agent handlers.

`run_instagram_account` is what the account bridge and the handlers registered as
`instagram.account.*` (the CLI) call, once each has read its payload with
`instagram_account_params`. What differs between the hosts is injected:
- `app`: the host's app lifecycle on the flow's package (`is_running()`, `restart()`). Every flow
  starts from a clean restart, except switching and listing accounts, which keep the screen
  Instagram already shows. None leaves the app as it is.
- `on_status(state, message)`: where that start is announced (the bridge's stdout, the CLI's log).
- `notifier`, `on_active_account`, `on_step`: the live narration the workflow accepts (the
  language change and the account switch); the bridge maps them to its events.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Mapping, Optional

from loguru import logger

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.instagram.workflows.management.language.change_language_workflow import (
    ChangeLanguageWorkflow,
)
from taktik.core.social_media.instagram.workflows.management.login import LoginWorkflow
from taktik.core.social_media.instagram.workflows.management.logout import LogoutWorkflow
from taktik.core.social_media.instagram.workflows.management.signup import SignupWorkflow
from taktik.core.social_media.instagram.workflows.management.switch import SwitchAccountWorkflow


INSTAGRAM_ACCOUNT_LOGIN_WORKFLOW_ID = "instagram.account.login"
INSTAGRAM_ACCOUNT_LOGOUT_WORKFLOW_ID = "instagram.account.logout"
INSTAGRAM_ACCOUNT_REGISTER_WORKFLOW_ID = "instagram.account.register"
INSTAGRAM_ACCOUNT_CHANGE_LANGUAGE_WORKFLOW_ID = "instagram.account.change_language"
INSTAGRAM_ACCOUNT_SWITCH_WORKFLOW_ID = "instagram.account.switch_account"
INSTAGRAM_ACCOUNT_LIST_WORKFLOW_ID = "instagram.account.list_accounts"
INSTAGRAM_ACCOUNT_LIST_SAVED_WORKFLOW_ID = "instagram.account.list_saved_accounts"
INSTAGRAM_ACCOUNT_WORKFLOW_IDS = (
    INSTAGRAM_ACCOUNT_LOGIN_WORKFLOW_ID,
    INSTAGRAM_ACCOUNT_LOGOUT_WORKFLOW_ID,
    INSTAGRAM_ACCOUNT_REGISTER_WORKFLOW_ID,
    INSTAGRAM_ACCOUNT_CHANGE_LANGUAGE_WORKFLOW_ID,
    INSTAGRAM_ACCOUNT_SWITCH_WORKFLOW_ID,
    INSTAGRAM_ACCOUNT_LIST_WORKFLOW_ID,
    INSTAGRAM_ACCOUNT_LIST_SAVED_WORKFLOW_ID,
)
#: Flows that act on the account picker (or home) Instagram already shows: a cold restart there
#: only lands back on the same picker.
KEEPS_CURRENT_SCREEN = (
    INSTAGRAM_ACCOUNT_SWITCH_WORKFLOW_ID,
    INSTAGRAM_ACCOUNT_LIST_WORKFLOW_ID,
    INSTAGRAM_ACCOUNT_LIST_SAVED_WORKFLOW_ID,
)
WorkflowFactory = Callable[..., Any]
AppProvider = Callable[[Optional[str]], Any]
StatusCallback = Callable[[str, str], None]


def start_instagram_for_account(app, workflow_id: str, on_status: Optional[StatusCallback] = None) -> None:
    """Bring Instagram to the state the account flow starts from."""
    if workflow_id in KEEPS_CURRENT_SCREEN and app.is_running():
        _status(on_status, "initializing", "Instagram already open — using the current screen")
        time.sleep(1)
        return
    _status(on_status, "initializing", "Restarting Instagram...")
    app.restart()
    time.sleep(2)


def run_instagram_account(
    workflow_id: str,
    params: Mapping[str, Any],
    *,
    device,
    device_id: str,
    app=None,
    on_status: Optional[StatusCallback] = None,
    notifier=None,
    on_active_account: Optional[Callable[[str], None]] = None,
    on_step: Optional[Callable[[str, dict], None]] = None,
    login_workflow_factory: WorkflowFactory = LoginWorkflow,
    logout_workflow_factory: WorkflowFactory = LogoutWorkflow,
    signup_workflow_factory: WorkflowFactory = SignupWorkflow,
    change_language_workflow_factory: WorkflowFactory = ChangeLanguageWorkflow,
    switch_workflow_factory: WorkflowFactory = SwitchAccountWorkflow,
) -> dict[str, Any]:
    """Run one Instagram account flow with already-read params."""
    if workflow_id not in INSTAGRAM_ACCOUNT_WORKFLOW_IDS:
        raise ValueError(f"Unsupported Instagram account workflow id: {workflow_id}")

    if app is not None:
        start_instagram_for_account(app, workflow_id, on_status)

    if workflow_id == INSTAGRAM_ACCOUNT_LOGIN_WORKFLOW_ID:
        return login_workflow_factory(device, device_id).execute(**params)
    if workflow_id == INSTAGRAM_ACCOUNT_LOGOUT_WORKFLOW_ID:
        return logout_workflow_factory(device, device_id).execute()
    if workflow_id == INSTAGRAM_ACCOUNT_REGISTER_WORKFLOW_ID:
        return signup_workflow_factory(device, device_id).execute(**params)
    if workflow_id == INSTAGRAM_ACCOUNT_CHANGE_LANGUAGE_WORKFLOW_ID:
        workflow = change_language_workflow_factory(device, device_id, notifier=notifier)
        return workflow.execute(language=params["language"])

    workflow = switch_workflow_factory(
        device, device_id, notifier=notifier, on_active_account=on_active_account, on_step=on_step,
    )
    if workflow_id == INSTAGRAM_ACCOUNT_SWITCH_WORKFLOW_ID:
        return workflow.execute(params["target_username"])
    if workflow_id == INSTAGRAM_ACCOUNT_LIST_WORKFLOW_ID:
        return workflow.list_accounts()
    return workflow.list_saved_accounts()


def instagram_account_params(workflow_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """The params of `workflow_id` read from a payload (page keys or snake_case).

    Raises ValueError, before any device work, when a required field is missing.
    """
    if workflow_id == INSTAGRAM_ACCOUNT_LOGIN_WORKFLOW_ID:
        return _login_params(payload)
    if workflow_id == INSTAGRAM_ACCOUNT_REGISTER_WORKFLOW_ID:
        return _register_params(payload)
    if workflow_id == INSTAGRAM_ACCOUNT_CHANGE_LANGUAGE_WORKFLOW_ID:
        return {
            "language": _required_string(
                payload, "language", message="language is required for change_language",
            ),
        }
    if workflow_id == INSTAGRAM_ACCOUNT_SWITCH_WORKFLOW_ID:
        return {
            "target_username": _required_string(
                payload, "targetUsername", "target_username",
                message="targetUsername is required for switch_account",
            ),
        }
    if workflow_id in INSTAGRAM_ACCOUNT_WORKFLOW_IDS:
        return {}
    raise ValueError(f"Unsupported Instagram account workflow id: {workflow_id}")


def build_instagram_account_handler(
    *,
    device,
    device_id: str,
    instagram_account_app: Optional[AppProvider] = None,
    login_workflow_factory: WorkflowFactory = LoginWorkflow,
    logout_workflow_factory: WorkflowFactory = LogoutWorkflow,
    signup_workflow_factory: WorkflowFactory = SignupWorkflow,
    change_language_workflow_factory: WorkflowFactory = ChangeLanguageWorkflow,
    switch_workflow_factory: WorkflowFactory = SwitchAccountWorkflow,
) -> WorkflowHandler:
    """Build an injectable Instagram account handler without bridge startup."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = _merge_invocation_payload(invocation, payload)
        params = instagram_account_params(invocation.workflow_id, merged)
        app = None
        if instagram_account_app is not None:
            app = instagram_account_app(_optional_string(merged, "packageName", "package_name"))
        return run_instagram_account(
            invocation.workflow_id,
            params,
            device=device,
            device_id=device_id,
            app=app,
            on_status=_log_status,
            login_workflow_factory=login_workflow_factory,
            logout_workflow_factory=logout_workflow_factory,
            signup_workflow_factory=signup_workflow_factory,
            change_language_workflow_factory=change_language_workflow_factory,
            switch_workflow_factory=switch_workflow_factory,
        )

    return handler


def register_instagram_account_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    device_id: str,
    instagram_account_app: Optional[AppProvider] = None,
    login_workflow_factory: WorkflowFactory = LoginWorkflow,
    logout_workflow_factory: WorkflowFactory = LogoutWorkflow,
    signup_workflow_factory: WorkflowFactory = SignupWorkflow,
    change_language_workflow_factory: WorkflowFactory = ChangeLanguageWorkflow,
    switch_workflow_factory: WorkflowFactory = SwitchAccountWorkflow,
) -> WorkflowRegistry:
    """Register Instagram account handlers into an injected Agent registry."""
    handler = build_instagram_account_handler(
        device=device,
        device_id=device_id,
        instagram_account_app=instagram_account_app,
        login_workflow_factory=login_workflow_factory,
        logout_workflow_factory=logout_workflow_factory,
        signup_workflow_factory=signup_workflow_factory,
        change_language_workflow_factory=change_language_workflow_factory,
        switch_workflow_factory=switch_workflow_factory,
    )
    for workflow_id in INSTAGRAM_ACCOUNT_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _status(on_status: Optional[StatusCallback], state: str, message: str) -> None:
    if on_status is not None:
        on_status(state, message)


def _log_status(state: str, message: str) -> None:
    logger.info(f"[{state}] {message}")


def _merge_invocation_payload(
    invocation: WorkflowInvocation,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(payload)
    merged.update(invocation.params)
    return merged


def _login_params(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "username": _required_string(
            payload,
            "username",
            message="Instagram login requires username",
        ),
        "password": _required_string(
            payload,
            "password",
            message="Instagram login requires password",
        ),
        "max_retries": _int_param(payload, "max_retries", "maxRetries", default=3),
        "save_session": _bool_param(payload, "save_session", "saveSession", default=True),
        "use_saved_session": _bool_param(
            payload,
            "use_saved_session",
            "useSavedSession",
            default=True,
        ),
        "save_login_info_instagram": _bool_param(
            payload,
            "save_login_info_instagram",
            "saveLoginInfoInstagram",
            default=False,
        ),
    }


def _register_params(payload: Mapping[str, Any]) -> dict[str, Any]:
    method = _string_param(payload, "method", default="email").lower()
    if method not in {"email", "phone"}:
        raise ValueError("Instagram register method must be 'email' or 'phone'")

    email = _optional_string(payload, "email")
    phone = _optional_string(payload, "phone")
    if method == "email" and not email:
        raise ValueError("Instagram register requires email when method is email")
    if method == "phone" and not phone:
        raise ValueError("Instagram register requires phone when method is phone")

    return {
        "method": method,
        "email": email,
        "phone": phone,
    }


def _required_string(payload: Mapping[str, Any], *names: str, message: str) -> str:
    value = _optional_string(payload, *names)
    if not value:
        raise ValueError(message)
    return value


def _optional_string(payload: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        value = payload.get(name)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _string_param(payload: Mapping[str, Any], name: str, *, default: str) -> str:
    value = payload.get(name)
    if value is None:
        return default
    return str(value).strip() or default


def _int_param(payload: Mapping[str, Any], *names: str, default: int) -> int:
    for name in names:
        value = payload.get(name)
        if value is not None:
            return int(value)
    return default


def _bool_param(payload: Mapping[str, Any], *names: str, default: bool) -> bool:
    for name in names:
        value = payload.get(name)
        if value is not None:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)
    return default
