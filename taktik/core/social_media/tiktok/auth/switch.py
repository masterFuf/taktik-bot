"""Switch between accounts already signed into TikTok's native account sheet."""

from __future__ import annotations

import re
import time
from typing import Any, Callable

from loguru import logger
from lxml import etree

from taktik.core.social_media.account_management import (
    AccountCatalog,
    is_account_username,
    normalize_account_username,
)
from taktik.core.social_media.tiktok.ui.selectors.shell.auth.account_switch import (
    ACCOUNT_SWITCH_SELECTORS,
)


_RESOURCE_ID_SELECTOR_RE = re.compile(r':id/([a-zA-Z0-9_]+)')


def _short_id(node) -> str:
    return (node.get("resource-id") or "").rsplit("/", 1)[-1]


def _normalize_username(value: Any) -> str:
    return normalize_account_username(value)


def _selector_resource_ids(selectors: list[str]) -> set[str]:
    """Return package-independent resource ID suffixes named by XPath selectors."""
    return {
        match
        for selector in selectors
        for match in _RESOURCE_ID_SELECTOR_RE.findall(selector)
    }


class TikTokSwitchAccount:
    """Native switcher for sessions TikTok already has signed in."""

    def __init__(
        self,
        device,
        device_id: str,
        *,
        android_user_id=None,
        notifier=None,
        sleeper: Callable[[float], None] | None = None,
        navigator_factory=None,
        max_attempts: int = 2,
        transition_timeout: float = 10.0,
        poll_interval: float = 0.5,
        clock: Callable[[], float] | None = None,
    ):
        self.device = device
        self.device_id = device_id
        self.android_user_id = android_user_id
        self.notifier = notifier
        self._sleep = sleeper or time.sleep
        self._navigator_factory = navigator_factory
        self.max_attempts = max(1, int(max_attempts))
        self.transition_timeout = max(0.0, float(transition_timeout))
        self.poll_interval = max(0.01, float(poll_interval))
        self._clock = clock or time.monotonic
        self.selectors = ACCOUNT_SWITCH_SELECTORS
        self.logger = logger.bind(module="tiktok-switch-account", device=device_id)

    def _dump_root(self):
        try:
            xml = self.device.dump_hierarchy(compressed=False)
            if not xml:
                return None
            return etree.fromstring(xml.encode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - unreadable UI is a safe workflow failure
            self.logger.debug(f"TikTok account hierarchy unavailable: {exc}")
            return None

    def _profile_username(self, root) -> str:
        if root is None:
            return ""
        # qh5 exists on every profile, including a creator we merely visited. Only the selected
        # Profile bottom tab proves this is our own account identity.
        own_profile = any(
            _short_id(node) in {"mks", "oeg", "ofe"} and node.get("selected") == "true"
            for node in root.iter()
        )
        if not own_profile:
            return ""
        username_ids = _selector_resource_ids(self.selectors.profile_username)
        for node in root.iter():
            text = node.get("text") or ""
            if _short_id(node) not in username_ids and not text.startswith("@"):
                continue
            username = _normalize_username(text)
            if is_account_username(username):
                return username
        return ""

    def _accounts(self, root) -> tuple[list[str], str, list[str]]:
        raw_accounts: list[str] = []
        active = ""
        if root is None:
            return [], active, []

        row_ids = _selector_resource_ids(self.selectors.account_rows)
        label_ids = _selector_resource_ids(self.selectors.username_labels)
        indicator_ids = _selector_resource_ids(self.selectors.active_indicators)
        rows = [row for row in root.iter() if _short_id(row) in row_ids]
        if not rows:
            sheets = [node for node in root.iter() if node.get("content-desc") == "Bottom sheet"]
            rows = [
                node
                for sheet in sheets
                for node in sheet.iter()
                if node.get("class") == "android.widget.Button"
                and node.get("clickable") == "true"
                and node.get("content-desc") not in (None, "", "Close")
            ]

        for row in rows:
            raw = row.get("content-desc") or ""
            if not raw:
                raw = next(
                    (
                        (child.get("text") or "")
                        for child in row.iter()
                        if _short_id(child) in label_ids
                    ),
                    "",
                )
            username = _normalize_username(raw)
            if not is_account_username(username) or username == "add.account":
                continue
            raw_accounts.append(username)
            selected = row.get("selected") == "true" or any(
                (
                    _short_id(child) in indicator_ids
                    or child.get("content-desc") == "Checkmark"
                )
                and child.get("selected") == "true"
                for child in row.iter()
            )
            if selected:
                active = username
        catalog = AccountCatalog.from_values(raw_accounts)
        return list(catalog.accounts), active, list(catalog.ambiguous)

    def _snapshot(self) -> tuple[Any, str, list[str], str, list[str]]:
        root = self._dump_root()
        profile = self._profile_username(root)
        accounts, selected, ambiguous = self._accounts(root)
        return root, profile, accounts, selected, ambiguous

    @staticmethod
    def _is_save_login_prompt(root) -> bool:
        if root is None:
            return False
        texts = {
            (node.get("text") or "").strip().lower()
            for node in root.iter()
            if node.get("text")
        }
        return "save login for next time?" in texts and "not now" in texts

    @staticmethod
    def _is_tiktok_shell(root) -> bool:
        if root is None:
            return False
        return any(
            _short_id(node) in {"mks", "oeg", "ofe"}
            and node.get("content-desc") == "Profile"
            and node.get("clickable") == "true"
            for node in root.iter()
        )

    @staticmethod
    def _is_login_screen(root) -> bool:
        """A password input is a strict signal that the signed-in session is unavailable."""
        if root is None:
            return False
        return any(
            node.get("class") == "android.widget.EditText"
            and node.get("password") == "true"
            for node in root.iter()
        )

    def _navigate_to_profile(self) -> bool:
        factory = self._navigator_factory
        if factory is None:
            from taktik.core.social_media.tiktok.actions.atomic.navigation.navigation_actions import (
                NavigationActions,
            )

            factory = NavigationActions
        try:
            return bool(factory(self.device).navigate_to_profile())
        except Exception as exc:  # noqa: BLE001
            self.logger.debug(f"Could not navigate to TikTok profile: {exc}")
            return False

    def _active_username(self, *, navigate: bool) -> str:
        _, profile, _, selected, _ = self._snapshot()
        if profile or selected:
            return profile or selected
        if not navigate or not self._navigate_to_profile():
            return ""
        _, profile, _, _, _ = self._snapshot()
        return profile

    def _click_first(self, selectors: list[str]) -> bool:
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    return True
            except Exception:
                continue
        return False

    def _open_switcher(self) -> tuple[list[str], str, list[str]] | None:
        _, profile, accounts, selected, ambiguous = self._snapshot()
        if accounts:
            return accounts, selected, ambiguous
        if not profile:
            if not self._navigate_to_profile():
                return None
            _, profile, _, _, _ = self._snapshot()
            if not profile:
                return None
        if not self._click_first(self.selectors.profile_switcher_button):
            return None
        deadline = self._clock() + self.transition_timeout
        while True:
            _, _, accounts, selected, ambiguous = self._snapshot()
            if accounts:
                return accounts, selected, ambiguous
            remaining = deadline - self._clock()
            if remaining <= 0:
                return None
            self._sleep(min(self.poll_interval, remaining))

    def _close_switcher(self) -> None:
        if self._click_first(self.selectors.close_button):
            return
        try:
            self.device.press("back")
        except Exception:
            pass

    def _verification_outcome(self, target: str) -> tuple[str, str]:
        """Wait for an observable post-selection state and return its classification."""
        verified = ""
        profile_navigation_attempts = 0
        deadline = self._clock() + self.transition_timeout
        while True:
            root, profile, visible_accounts, _, _ = self._snapshot()
            if self._is_login_screen(root):
                return "session_expired", verified
            if profile:
                verified = profile
                if verified == target:
                    return "verified", verified
            if self._is_save_login_prompt(root):
                self._click_first(self.selectors.post_switch_prompt_dismiss)
            elif (
                not visible_accounts
                and self._is_tiktok_shell(root)
                and profile_navigation_attempts < 3
            ):
                profile_navigation_attempts += 1
                self._navigate_to_profile()
            remaining = deadline - self._clock()
            if remaining <= 0:
                return "verification_failed", verified
            self._sleep(min(self.poll_interval, remaining))

    def _switch_failure(
        self,
        *,
        target: str,
        previous: str,
        active: str,
        accounts: list[str],
        attempts: int,
        error_type: str,
        stage: str,
        category: str,
        message: str,
        ambiguous: list[str] | None = None,
        state_known: bool | None = None,
    ) -> dict[str, Any]:
        known = bool(active) if state_known is None else state_known
        self.logger.warning(
            f"TikTok switch current=@{active or '?'} target=@{target} "
            f"attempt={attempts}/{self.max_attempts} stage={stage} error={error_type}"
        )
        return self._result(
            success=False,
            workflow="switch_account",
            requested_username=target,
            previous_username=previous or None,
            active_username=active or None,
            accounts=accounts,
            ambiguous_accounts=ambiguous or [],
            already_active=False,
            attempts=attempts,
            failure_stage=stage,
            failure_category=category,
            state_known=known,
            relogin_required=error_type == "session_expired",
            error_type=error_type,
            message=message,
        )

    def _result(self, *, success: bool, workflow: str, **values) -> dict[str, Any]:
        return {
            "success": success,
            "workflow": workflow,
            "device_id": self.device_id,
            "android_user_id": self.android_user_id,
            **values,
        }

    def _android_user_failure(self, workflow: str) -> dict[str, Any] | None:
        """Return a structured failure when an explicit Android profile is not active."""
        if self.android_user_id is None:
            return None
        try:
            requested = int(self.android_user_id)
            if requested < 0:
                raise ValueError
        except (TypeError, ValueError):
            return self._result(
                success=False,
                workflow=workflow,
                error_type="invalid_android_user",
                message="androidUserId must be a non-negative integer",
            )
        self.android_user_id = requested
        try:
            response = self.device.shell("am get-current-user")
            output = getattr(response, "output", response)
            current = int(str(output).strip())
        except Exception as exc:  # noqa: BLE001
            return self._result(
                success=False,
                workflow=workflow,
                error_type="android_user_unverified",
                message=f"Could not verify androidUserId {requested}: {exc}",
            )
        if current == requested:
            return None
        return self._result(
            success=False,
            workflow=workflow,
            error_type="android_user_mismatch",
            message=f"androidUserId {requested} is not active (current: {current})",
        )

    def list_accounts(self):
        """Return accounts visible in the native switcher without selecting one."""
        android_user_failure = self._android_user_failure("list_accounts")
        if android_user_failure:
            return android_user_failure
        active = self._active_username(navigate=True)
        opened = self._open_switcher()
        if opened is None:
            return self._result(
                success=False,
                workflow="list_accounts",
                active_username=active or None,
                accounts=[active] if active else [],
                error_type="switcher_unavailable",
                message="TikTok account switcher could not be opened",
            )
        accounts, selected, ambiguous = opened
        active = selected or active
        self._close_switcher()
        return self._result(
            success=True,
            workflow="list_accounts",
            active_username=active or None,
            accounts=accounts,
            ambiguous_accounts=ambiguous,
            error_type=None,
            message=f"Found {len(accounts)} signed-in TikTok account(s)",
        )

    def switch_account(self, target_username: str):
        """Select and verify one account already present in TikTok's switcher."""
        target = _normalize_username(target_username)
        if not is_account_username(target):
            return self._result(
                success=False,
                workflow="switch_account",
                requested_username=target or None,
                active_username=None,
                accounts=[],
                already_active=False,
                attempts=0,
                failure_stage="validate",
                failure_category="account_not_found",
                state_known=False,
                error_type="invalid_target",
                message="targetUsername is not a valid TikTok username",
            )

        android_user_failure = self._android_user_failure("switch_account")
        if android_user_failure:
            return {
                **android_user_failure,
                "requested_username": target,
                "active_username": None,
                "accounts": [],
                "already_active": False,
            }

        root, profile, _, selected, _ = self._snapshot()
        if self._is_login_screen(root):
            return self._switch_failure(
                target=target,
                previous="",
                active="",
                accounts=[],
                attempts=0,
                error_type="session_expired",
                stage="detect_active",
                category="login_session_expired",
                message="TikTok login session is expired or unavailable",
                state_known=True,
            )
        active = profile or selected or self._active_username(navigate=True)
        previous = active
        if active == target:
            return self._result(
                success=True,
                workflow="switch_account",
                requested_username=target,
                active_username=active,
                accounts=[active],
                already_active=True,
                previous_username=active,
                attempts=0,
                failure_stage=None,
                failure_category=None,
                state_known=True,
                ambiguous_accounts=[],
                error_type=None,
                message=f"@{target} is already active",
            )

        accounts: list[str] = []
        ambiguous: list[str] = []
        last_failure: dict[str, Any] | None = None
        for attempt in range(1, self.max_attempts + 1):
            self.logger.info(
                f"TikTok switch current=@{active or '?'} target=@{target} "
                f"attempt={attempt}/{self.max_attempts} stage=open_switcher"
            )
            opened = self._open_switcher()
            if opened is None:
                root, profile, _, selected, _ = self._snapshot()
                if self._is_login_screen(root):
                    return self._switch_failure(
                        target=target,
                        previous=previous,
                        active="",
                        accounts=accounts,
                        attempts=attempt,
                        error_type="session_expired",
                        stage="open_switcher",
                        category="login_session_expired",
                        message="TikTok login session is expired or unavailable",
                        state_known=True,
                    )
                active = profile or selected or active
                last_failure = self._switch_failure(
                    target=target,
                    previous=previous,
                    active=active,
                    accounts=accounts,
                    attempts=attempt,
                    error_type="switcher_unavailable",
                    stage="open_switcher",
                    category="selector_not_found" if active else "ui_navigation_failure",
                    message="TikTok account switcher could not be opened",
                )
                continue

            accounts, selected, ambiguous = opened
            active = selected or active
            if target in ambiguous:
                self._close_switcher()
                return self._switch_failure(
                    target=target,
                    previous=previous,
                    active=active,
                    accounts=accounts,
                    ambiguous=ambiguous,
                    attempts=attempt,
                    error_type="ambiguous_target",
                    stage="lookup",
                    category="account_not_found",
                    message=f"Multiple TikTok account rows match @{target}",
                )
            if target not in accounts:
                self._close_switcher()
                return self._switch_failure(
                    target=target,
                    previous=previous,
                    active=active,
                    accounts=accounts,
                    ambiguous=ambiguous,
                    attempts=attempt,
                    error_type="target_not_found",
                    stage="lookup",
                    category="account_not_found",
                    message=f"@{target} is not signed into TikTok on this device",
                )

            if not self._click_first(self.selectors.account_row(target)):
                self._close_switcher()
                last_failure = self._switch_failure(
                    target=target,
                    previous=previous,
                    active=active,
                    accounts=accounts,
                    ambiguous=ambiguous,
                    attempts=attempt,
                    error_type="selection_failed",
                    stage="select",
                    category="selector_not_found",
                    message=f"Could not select @{target}",
                )
                continue

            outcome, verified = self._verification_outcome(target)
            if outcome == "verified":
                self.logger.info(
                    f"TikTok switch current=@{verified} target=@{target} "
                    f"attempt={attempt}/{self.max_attempts} stage=verified"
                )
                return self._result(
                    success=True,
                    workflow="switch_account",
                    requested_username=target,
                    previous_username=previous or None,
                    active_username=verified,
                    accounts=accounts,
                    ambiguous_accounts=ambiguous,
                    already_active=False,
                    attempts=attempt,
                    failure_stage=None,
                    failure_category=None,
                    state_known=True,
                    error_type=None,
                    message=f"Switched to and verified @{target}",
                )
            if outcome == "session_expired":
                return self._switch_failure(
                    target=target,
                    previous=previous,
                    active=verified,
                    accounts=accounts,
                    ambiguous=ambiguous,
                    attempts=attempt,
                    error_type="session_expired",
                    stage="verify",
                    category="login_session_expired",
                    message=f"@{target} requires login again",
                    state_known=True,
                )

            # Once the row was tapped, the old identity is historical only. Report current
            # state solely when it can be observed after the attempted transition.
            active = verified or self._active_username(navigate=True)
            last_failure = self._switch_failure(
                target=target,
                previous=previous,
                active=active,
                accounts=accounts,
                ambiguous=ambiguous,
                attempts=attempt,
                error_type="verification_failed",
                stage="verify",
                category="switch_verification_failed",
                message=f"TikTok did not verify @{target} after selection",
            )

        return last_failure or self._switch_failure(
            target=target,
            previous=previous,
            active=active,
            accounts=accounts,
            ambiguous=ambiguous,
            attempts=self.max_attempts,
            error_type="switcher_unavailable",
            stage="open_switcher",
            category="ui_navigation_failure",
            message="TikTok account switch attempts exhausted",
        )


__all__ = ["TikTokSwitchAccount"]
