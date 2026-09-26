"""The one launcher of the TikTok account workflows, and their Agent handlers.

`run_tiktok_account` is what the account bridge and the handlers registered as `tiktok.account.*`
(the CLI) call, once each has read its payload with `tiktok_account_params`. What differs between
the hosts is injected:
- `app`: the host's app lifecycle on the flow's package (`restart()`, `package`). Every flow
  starts from a clean restart, a cloned TikTok's selectors patched. None leaves the app as it is.
- `notifier`: shaped like the bridge IPC (`status`, `log`, `send`); the workflows narrate through it.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Mapping, Optional

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    bool_param,
    int_param,
    merge_invocation_payload,
    value_param,
)
from taktik.core.social_media.tiktok.workflows.management.language.change_language_workflow import (
    TikTokChangeLanguageWorkflow,
)
from taktik.core.social_media.tiktok.workflows.management.login.login_workflow import (
    TikTokLoginWorkflow,
)
from taktik.core.social_media.tiktok.workflows.management.logout.logout_workflow import (
    TikTokLogoutWorkflow,
)
from taktik.core.social_media.tiktok.workflows.management.signup.signup_workflow import (
    TikTokSignupWorkflow,
)
from taktik.core.social_media.tiktok.workflows.runtime.startup import patch_clone_selectors


TIKTOK_ACCOUNT_LOGIN_WORKFLOW_ID = "tiktok.account.login"
TIKTOK_ACCOUNT_LOGOUT_WORKFLOW_ID = "tiktok.account.logout"
TIKTOK_ACCOUNT_REGISTER_WORKFLOW_ID = "tiktok.account.register"
TIKTOK_ACCOUNT_CHANGE_LANGUAGE_WORKFLOW_ID = "tiktok.account.change_language"
TIKTOK_ACCOUNT_WORKFLOW_IDS = (
    TIKTOK_ACCOUNT_LOGIN_WORKFLOW_ID,
    TIKTOK_ACCOUNT_LOGOUT_WORKFLOW_ID,
    TIKTOK_ACCOUNT_REGISTER_WORKFLOW_ID,
    TIKTOK_ACCOUNT_CHANGE_LANGUAGE_WORKFLOW_ID,
)
WorkflowFactory = Callable[..., Any]
AppProvider = Callable[[Optional[str]], Any]


def start_tiktok_for_account(app, notifier=None) -> None:
    """Clean restart (force-stop, launch) for a known initial state, like every bridge."""
    _emit(notifier, "status", "initializing", "Restarting TikTok...")
    app.restart()
    patch_clone_selectors(app.package, notifier)
    time.sleep(2)


def run_tiktok_account(
    workflow_id: str,
    params: Mapping[str, Any],
    *,
    device,
    device_id: str,
    app=None,
    notifier=None,
    login_workflow_factory: WorkflowFactory = TikTokLoginWorkflow,
    logout_workflow_factory: WorkflowFactory = TikTokLogoutWorkflow,
    signup_workflow_factory: WorkflowFactory = TikTokSignupWorkflow,
    change_language_workflow_factory: WorkflowFactory = TikTokChangeLanguageWorkflow,
) -> dict[str, Any]:
    """Run one TikTok account flow with already-read params."""
    if workflow_id not in TIKTOK_ACCOUNT_WORKFLOW_IDS:
        raise ValueError(f"Unsupported TikTok account workflow id: {workflow_id}")

    if app is not None:
        start_tiktok_for_account(app, notifier)

    if workflow_id == TIKTOK_ACCOUNT_LOGIN_WORKFLOW_ID:
        return login_workflow_factory(device, device_id, notifier=notifier).execute(**params)
    if workflow_id == TIKTOK_ACCOUNT_LOGOUT_WORKFLOW_ID:
        return logout_workflow_factory(device, device_id, notifier=notifier).execute()
    if workflow_id == TIKTOK_ACCOUNT_REGISTER_WORKFLOW_ID:
        return signup_workflow_factory(device, device_id, notifier=notifier).execute(**params)
    workflow = change_language_workflow_factory(device, device_id, notifier=notifier)
    return workflow.run(params["target_language"])


def tiktok_account_params(workflow_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """The params of `workflow_id` read from a payload (page keys or snake_case).

    Raises ValueError, before any device work, when a required field is missing.
    """
    if workflow_id == TIKTOK_ACCOUNT_LOGIN_WORKFLOW_ID:
        return _login_params(payload)
    if workflow_id == TIKTOK_ACCOUNT_REGISTER_WORKFLOW_ID:
        return _register_params(payload)
    if workflow_id == TIKTOK_ACCOUNT_CHANGE_LANGUAGE_WORKFLOW_ID:
        # Refused rather than defaulted: a missing field must not change what the phone speaks.
        return {
            "target_language": _required_string(
                payload, "targetLanguage", "target_language", "language",
                message="targetLanguage is required (e.g. 'fr', 'en', 'en-US')",
            ),
        }
    if workflow_id == TIKTOK_ACCOUNT_LOGOUT_WORKFLOW_ID:
        return {}
    raise ValueError(f"Unsupported TikTok account workflow id: {workflow_id}")


def build_tiktok_account_handler(
    *,
    device,
    device_id: str,
    notifier=None,
    tiktok_account_app: Optional[AppProvider] = None,
    login_workflow_factory: WorkflowFactory = TikTokLoginWorkflow,
    logout_workflow_factory: WorkflowFactory = TikTokLogoutWorkflow,
    signup_workflow_factory: WorkflowFactory = TikTokSignupWorkflow,
    change_language_workflow_factory: WorkflowFactory = TikTokChangeLanguageWorkflow,
) -> WorkflowHandler:
    """Build an injectable TikTok account handler without bridge startup."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = merge_invocation_payload(invocation, payload)
        params = tiktok_account_params(invocation.workflow_id, merged)
        app = None
        if tiktok_account_app is not None:
            app = tiktok_account_app(_optional_string(merged, "packageName", "package_name"))
        return run_tiktok_account(
            invocation.workflow_id,
            params,
            device=device,
            device_id=device_id,
            app=app,
            notifier=notifier,
            login_workflow_factory=login_workflow_factory,
            logout_workflow_factory=logout_workflow_factory,
            signup_workflow_factory=signup_workflow_factory,
            change_language_workflow_factory=change_language_workflow_factory,
        )

    return handler


def register_tiktok_account_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    device_id: str,
    notifier=None,
    tiktok_account_app: Optional[AppProvider] = None,
    login_workflow_factory: WorkflowFactory = TikTokLoginWorkflow,
    logout_workflow_factory: WorkflowFactory = TikTokLogoutWorkflow,
    signup_workflow_factory: WorkflowFactory = TikTokSignupWorkflow,
    change_language_workflow_factory: WorkflowFactory = TikTokChangeLanguageWorkflow,
) -> WorkflowRegistry:
    """Register TikTok account handlers into an injected Agent registry."""
    handler = build_tiktok_account_handler(
        device=device,
        device_id=device_id,
        notifier=notifier,
        tiktok_account_app=tiktok_account_app,
        login_workflow_factory=login_workflow_factory,
        logout_workflow_factory=logout_workflow_factory,
        signup_workflow_factory=signup_workflow_factory,
        change_language_workflow_factory=change_language_workflow_factory,
    )
    for workflow_id in TIKTOK_ACCOUNT_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _emit(notifier: Any, method: str, *args: Any) -> None:
    target = getattr(notifier, method, None)
    if callable(target):
        target(*args)


def _login_params(payload: Mapping[str, Any]) -> dict[str, Any]:
    username = _required_string(payload, "username", message="TikTok login requires username")
    password = _required_string(payload, "password", message="TikTok login requires password")
    return {
        "username": username,
        "password": password,
        "max_retries": int_param(payload, "max_retries", "maxRetries", default=3),
        "save_session": bool_param(payload, "save_session", "saveSession", default=True),
    }


def _register_params(payload: Mapping[str, Any]) -> dict[str, Any]:
    method = str(value_param(payload, "method", default="email")).strip().lower()
    if method not in {"email", "phone"}:
        raise ValueError("TikTok register method must be 'email' or 'phone'")

    email = _optional_string(payload, "email")
    phone = _optional_string(payload, "phone")
    if method == "email" and not email:
        raise ValueError("TikTok register requires email when method is email")
    if method == "phone" and not phone:
        raise ValueError("TikTok register requires phone when method is phone")

    return {
        "method": method,
        "email": email,
        "phone": phone,
        "phone_country": _optional_string(payload, "phone_country", "phoneCountry"),
        "birth_year": int_param(payload, "birth_year", "birthYear", default=1995),
        "birth_month": int_param(payload, "birth_month", "birthMonth", default=6),
        "birth_day": int_param(payload, "birth_day", "birthDay", default=15),
        "gmail_password": _optional_string(payload, "gmail_password", "gmailPassword"),
        "tiktok_password": _optional_string(payload, "tiktok_password", "tiktokPassword"),
        "nickname": _optional_string(payload, "nickname"),
    }


def _required_string(payload: Mapping[str, Any], *names: str, message: str) -> str:
    value = _optional_string(payload, *names)
    if not value:
        raise ValueError(message)
    return value


def _optional_string(payload: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        value = value_param(payload, name, default=None)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None
