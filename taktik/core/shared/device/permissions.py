"""
Android Permission Dialog Handler
==================================
Centralised service for detecting and dismissing Android permission popups.

Android versions change the package that hosts the permission UI:
  - Android  ≤ 9  (SDK ≤ 28) : com.android.packageinstaller
  - Android 10-12 (SDK 29-32) : com.android.permissioncontroller
  - Android 13+   (SDK 33+)   : com.android.permissioncontroller  (unchanged pkg,
                                  but new "Allow" button IDs for media/photos split)

Button resolution strategy (highest to lowest priority):
  1. Resource-ID match (exact package + widget id)   → most reliable
  2. content-desc match                              → reliable on EN/FR
  3. text match (exact, then contains)               → handles case variations
     e.g. "AUTORISER" (FR, Android 9) vs "Autoriser" (FR, Android 10+)

Usage
-----
from taktik.core.shared.device.permissions import PermissionHandler

handler = PermissionHandler(device, device_id)   # device_id used for SDK probe

# Grant any stacked permission dialogs that appear:
dismissed = handler.grant(rounds=3)

# Deny (notification opt-ins, etc.):
dismissed = handler.deny(rounds=2)

# Check if a dialog is currently visible without acting:
is_visible = handler.is_visible()
"""

from __future__ import annotations

import time
from typing import Optional

from loguru import logger

# Reuse the SDK-version helper already present in this package
from .media_store import get_android_sdk_version


# ---------------------------------------------------------------------------
# Selector tables  (XPath strings)
# ---------------------------------------------------------------------------

# ── "Allow" / "Autoriser" buttons ────────────────────────────────────────────
# Listed from most-specific to least-specific so _try_tap() hits the right one
# immediately instead of iterating through every entry.

_ALLOW_RESOURCE_IDS = [
    # Android 10+ — permissioncontroller
    "com.android.permissioncontroller:id/permission_allow_foreground_only_button",
    "com.android.permissioncontroller:id/permission_allow_one_time_button",
    "com.android.permissioncontroller:id/permission_allow_button",
    # Android 13+ media split (photos, videos, audio grants separately)
    "com.android.permissioncontroller:id/permission_allow_selected_button",
    # Android 9 — packageinstaller
    "com.android.packageinstaller:id/permission_allow_button",
    # MIUI (Xiaomi) custom permission UI
    "com.miui.securitycenter:id/btn_agree",
]

_ALLOW_TEXT_EN = [
    "While using the app",
    "WHILE USING THE APP",
    "Only this time",
    "Allow",
    "ALLOW",
]

_ALLOW_TEXT_FR = [
    "Pendant l'utilisation",
    "PENDANT L'UTILISATION",
    "Cette fois uniquement",
    "Autoriser",
    "AUTORISER",
]

# ── "Deny" / "Refuse" buttons ─────────────────────────────────────────────────

_DENY_RESOURCE_IDS = [
    "com.android.permissioncontroller:id/permission_deny_button",
    "com.android.permissioncontroller:id/permission_deny_and_dont_ask_again_button",
    "com.android.packageinstaller:id/permission_deny_button",
    "com.miui.securitycenter:id/btn_cancel",
]

_DENY_TEXT_EN = [
    "Don't allow",
    "DON'T ALLOW",
    "Deny",
    "No thanks",
    "Not now",
]

_DENY_TEXT_FR = [
    "Ne pas autoriser",
    "NE PAS AUTORISER",
    "Refuser",
    "Non merci",
    "Pas maintenant",
]

# ── Detection indicators (any of these → permission dialog is on screen) ──────

_DIALOG_RESOURCE_IDS = [
    # Android 10+ root container
    "com.android.permissioncontroller:id/grant_dialog",
    # Allow buttons double as indicators
    "com.android.permissioncontroller:id/permission_allow_foreground_only_button",
    "com.android.permissioncontroller:id/permission_allow_one_time_button",
    "com.android.permissioncontroller:id/permission_allow_button",
    "com.android.permissioncontroller:id/permission_allow_selected_button",
    # Android 9 root container
    "com.android.packageinstaller:id/grant_singleton",
    "com.android.packageinstaller:id/permission_allow_button",
    # MIUI
    "com.miui.securitycenter:id/btn_agree",
]


# ---------------------------------------------------------------------------
# XPath builder helpers
# ---------------------------------------------------------------------------

def _rid(resource_id: str) -> str:
    """XPath selector for an element with an exact resource-id."""
    return f'//*[@resource-id="{resource_id}"]'


def _text_exact(text: str) -> str:
    """XPath selector for a Button with an exact text."""
    return f'//android.widget.Button[@text="{text}"]'


def _text_contains(text: str) -> str:
    """XPath selector for a Button whose text contains the substring."""
    return f'//android.widget.Button[contains(@text, "{text}")]'


def _build_selectors(resource_ids: list[str], texts_en: list[str], texts_fr: list[str]) -> list[str]:
    """
    Assemble an ordered selector list: resource-ids first (most reliable),
    then exact-text matches (EN then FR), then contains-text fallbacks.
    """
    selectors: list[str] = []
    for rid in resource_ids:
        selectors.append(_rid(rid))
    for t in texts_en + texts_fr:
        selectors.append(_text_exact(t))
    # contains-text as last resort (handles partial / case variations we may have missed)
    for t in ["Allow", "ALLOW", "Autoriser", "AUTORISER", "While using", "Pendant"]:
        selectors.append(_text_contains(t))
    return selectors


# Pre-built selector lists (module-level constants, built once)
# These are used as fallback when SDK is unknown.  PermissionHandler builds an
# SDK-aware version lazily via _build_allow_selectors_for_sdk() so that the
# most likely resource-id for the detected Android version is tried FIRST,
# avoiding up to 4 × 4 s timeouts on wrong-version selectors.
ALLOW_SELECTORS: list[str] = _build_selectors(_ALLOW_RESOURCE_IDS, _ALLOW_TEXT_EN, _ALLOW_TEXT_FR)
DENY_SELECTORS: list[str] = _build_selectors(_DENY_RESOURCE_IDS, _DENY_TEXT_EN, _DENY_TEXT_FR)


def _build_allow_selectors_for_sdk(sdk: int) -> list[str]:
    """
    Build an Allow-button selector list with SDK-appropriate resource-ids first.

    Effect: the correct Allow button is tried before spending 4 s each on
    resource-ids that belong to a different Android version.

    Android 9  (SDK ≤ 28) : packageinstaller:id/permission_allow_button
    Android 10-12 (SDK 29-32) : permissioncontroller basic buttons
    Android 13+ (SDK 33+) : permissioncontroller + media-split selected button
    """
    if sdk <= 28:
        # Android 9 — com.android.packageinstaller hosts the dialog.
        # Skip the 4 permissioncontroller IDs entirely (they don't exist).
        rid_list = [
            "com.android.packageinstaller:id/permission_allow_button",
            # Keep as fallback: some OEMs on Android 9 still use permissioncontroller
            "com.android.permissioncontroller:id/permission_allow_button",
            "com.miui.securitycenter:id/btn_agree",
        ]
    elif sdk >= 33:
        # Android 13+ — media/photos/audio permissions split into separate dialogs.
        # "Allow selected" is the new primary choice; the rest are fallbacks.
        rid_list = [
            "com.android.permissioncontroller:id/permission_allow_selected_button",
            "com.android.permissioncontroller:id/permission_allow_foreground_only_button",
            "com.android.permissioncontroller:id/permission_allow_one_time_button",
            "com.android.permissioncontroller:id/permission_allow_button",
            "com.android.packageinstaller:id/permission_allow_button",
            "com.miui.securitycenter:id/btn_agree",
        ]
    else:
        # Android 10-12 — permissioncontroller, foreground/one-time first.
        rid_list = [
            "com.android.permissioncontroller:id/permission_allow_foreground_only_button",
            "com.android.permissioncontroller:id/permission_allow_one_time_button",
            "com.android.permissioncontroller:id/permission_allow_button",
            "com.android.packageinstaller:id/permission_allow_button",
            "com.miui.securitycenter:id/btn_agree",
        ]
    return _build_selectors(rid_list, _ALLOW_TEXT_EN, _ALLOW_TEXT_FR)
DIALOG_INDICATORS: list[str] = [_rid(r) for r in _DIALOG_RESOURCE_IDS] + [
    _text_exact("AUTORISER"),
    _text_exact("Autoriser"),
    _text_exact("ALLOW"),
    _text_exact("Allow"),
    _text_contains("WHILE USING"),
    _text_contains("While using"),
    _text_contains("Pendant l"),
]

CONTACT_PERMISSION_TEXTS = [
    "access your contacts",
    "access to your contacts",
    "accéder à vos contacts",
    "acceder a vos contacts",
    "contacts",
]


# ---------------------------------------------------------------------------
# Low-level XPath helpers (device-agnostic, work with any uiautomator2 device)
# ---------------------------------------------------------------------------

def _try_tap(device, selectors: list[str], timeout: float = 3.0) -> bool:
    """Try XPath selectors in order; tap the first that appears. Returns True on success."""
    for sel in selectors:
        try:
            el = device.xpath(sel)
            if el.wait(timeout=timeout):
                el.click()
                return True
        except Exception:
            pass
    return False


def _wait_for_any(device, selectors: list[str], timeout: float = 5.0) -> Optional[str]:
    """Return the first selector that becomes visible within `timeout` seconds, else None."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for sel in selectors:
            try:
                if device.xpath(sel).exists:
                    return sel
            except Exception:
                pass
        time.sleep(0.4)
    return None


# ---------------------------------------------------------------------------
# Public API — PermissionHandler
# ---------------------------------------------------------------------------

class PermissionHandler:
    """
    Stateful permission-dialog helper bound to a specific uiautomator2 device.

    The handler probes the Android SDK version once (lazily, on first use) and
    uses that information to log meaningful messages.  The selector lists are
    already exhaustive across all SDK versions, so the SDK level is currently
    used for logging only — it's available as `self.sdk` if callers need it.

    Parameters
    ----------
    device      uiautomator2 Device object (or DeviceManager).
    device_id   ADB serial used to run `getprop ro.build.version.sdk`.
    """

    def __init__(self, device, device_id: str = ""):
        # Unwrap DeviceManager → raw u2 device if needed
        if hasattr(device, "device") and device.device is not None:
            self._d = device.device
        else:
            self._d = device
        self._device_id = device_id
        self._sdk: Optional[int] = None  # lazy

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def sdk(self) -> int:
        """Android API level. Probed once via ADB, then cached."""
        if self._sdk is None:
            if self._device_id:
                self._sdk = get_android_sdk_version(self._device_id)
            else:
                # Fallback: try dumpsys from u2 shell
                try:
                    out = self._d.shell("getprop ro.build.version.sdk").output.strip()
                    self._sdk = int(out)
                except Exception:
                    self._sdk = 28  # safe default (Android 9)
            logger.debug(f"[PermissionHandler] SDK={self._sdk} (Android {self._sdk_to_name()})")
        return self._sdk

    def _sdk_to_name(self) -> str:
        sdk = self._sdk or 28
        mapping = {
            28: "9", 29: "10", 30: "11", 31: "12", 32: "12L", 33: "13", 34: "14", 35: "15",
        }
        return mapping.get(sdk, str(sdk))

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def is_visible(self, timeout: float = 2.0) -> bool:
        """Return True if a permission dialog appears to be on screen."""
        return _wait_for_any(self._d, DIALOG_INDICATORS, timeout=timeout) is not None

    def _dump_text(self) -> str:
        try:
            if hasattr(self._d, "dump_hierarchy"):
                return (self._d.dump_hierarchy() or "").lower()
        except Exception:
            pass
        return ""

    def is_contacts_permission_visible(self, timeout: float = 1.5) -> bool:
        """Return True if the visible permission dialog is specifically about contacts."""
        if not self.is_visible(timeout=timeout):
            return False
        dump = self._dump_text()
        return any(token in dump for token in CONTACT_PERMISSION_TEXTS)

    # ------------------------------------------------------------------
    # Grant / Deny
    # ------------------------------------------------------------------

    @property
    def _allow_selectors(self) -> list[str]:
        """SDK-optimised Allow selector list, built once per PermissionHandler instance."""
        if not hasattr(self, "_cached_allow_selectors"):
            self._cached_allow_selectors = _build_allow_selectors_for_sdk(self.sdk)
        return self._cached_allow_selectors

    def grant(self, rounds: int = 3, per_round_wait: float = 3.0) -> int:
        """
        Tap "Allow / Autoriser" on up to `rounds` stacked permission dialogs.

        Returns the number of dialogs successfully dismissed.
        """
        dismissed = 0
        for i in range(rounds):
            if not _wait_for_any(self._d, DIALOG_INDICATORS, timeout=per_round_wait):
                break
            logger.info(
                f"[PermissionHandler] 🔐 Permission dialog #{i + 1} on Android {self._sdk_to_name()} — granting"
            )
            if _try_tap(self._d, self._allow_selectors, timeout=4.0):
                dismissed += 1
                time.sleep(0.8)
            else:
                logger.warning("[PermissionHandler] ⚠️  Dialog visible but could not tap Allow — stopping")
                break
        if dismissed:
            logger.info(f"[PermissionHandler] ✅ Granted {dismissed} permission dialog(s)")
        return dismissed

    def deny(self, rounds: int = 2, per_round_wait: float = 3.0) -> int:
        """
        Tap "Deny / Ne pas autoriser" on up to `rounds` stacked permission dialogs.

        Returns the number of dialogs successfully dismissed.
        """
        dismissed = 0
        for i in range(rounds):
            if not _wait_for_any(self._d, DIALOG_INDICATORS, timeout=per_round_wait):
                break
            logger.info(
                f"[PermissionHandler] 🔕 Permission dialog #{i + 1} on Android {self._sdk_to_name()} — denying"
            )
            if _try_tap(self._d, DENY_SELECTORS, timeout=4.0):
                dismissed += 1
                time.sleep(0.8)
            else:
                logger.warning("[PermissionHandler] ⚠️  Dialog visible but could not tap Deny — stopping")
                break
        if dismissed:
            logger.info(f"[PermissionHandler] 🔕 Denied {dismissed} permission dialog(s)")
        return dismissed

    # ------------------------------------------------------------------
    # Convenience: grant_if_present (single shot, no loop)
    # ------------------------------------------------------------------

    def grant_if_present(self, wait: float = 3.0) -> bool:
        """Dismiss a single permission dialog if visible. Returns True if one was dismissed."""
        return self.grant(rounds=1, per_round_wait=wait) > 0

    def deny_if_present(self, wait: float = 3.0) -> bool:
        """Deny a single permission dialog if visible. Returns True if one was dismissed."""
        return self.deny(rounds=1, per_round_wait=wait) > 0

    def deny_contacts_if_present(self, wait: float = 1.5) -> bool:
        """Deny the Android contacts permission popup when it appears."""
        if not self.is_contacts_permission_visible(timeout=wait):
            return False
        logger.info(
            f"[PermissionHandler] Contacts permission detected on Android {self._sdk_to_name()} - denying"
        )
        return self.deny(rounds=1, per_round_wait=0.5) > 0


# ---------------------------------------------------------------------------
# Module-level convenience functions (no PermissionHandler instance needed)
# ---------------------------------------------------------------------------

def grant_permissions(device, device_id: str = "", rounds: int = 3, per_round_wait: float = 3.0) -> int:
    """Shorthand: create a PermissionHandler and call grant()."""
    return PermissionHandler(device, device_id).grant(rounds=rounds, per_round_wait=per_round_wait)


def deny_permissions(device, device_id: str = "", rounds: int = 2, per_round_wait: float = 3.0) -> int:
    """Shorthand: create a PermissionHandler and call deny()."""
    return PermissionHandler(device, device_id).deny(rounds=rounds, per_round_wait=per_round_wait)
