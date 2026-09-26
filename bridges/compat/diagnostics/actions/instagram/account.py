"""Account-lifecycle actions for Instagram compat diagnostics (Cartography Lab).

Login / logout / signup via the production ``InstagramLogin`` / ``InstagramLogout`` /
``InstagramSignup`` classes, built on the warm Lab device. These act on AUTH screens — run
them on a TEST account. Credentials are passed as params for the test and are NEVER logged.
"""

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


def _device_id(a):
    return getattr(a.device, "device_id", None) or "lab"


def _result(r, fallback):
    """Serialize a LoginResult/LogoutResult/SignupResult (success + message + extras)."""
    try:
        d = dict(vars(r))
    except TypeError:
        return {"success": bool(r), "message": fallback}
    return {"success": bool(d.get("success")), "message": d.get("message") or fallback, "details": d}


def _login(a):
    from taktik.core.social_media.instagram.auth.login import InstagramLogin
    return InstagramLogin(a.device, _device_id(a))


def _logout(a):
    from taktik.core.social_media.instagram.auth.logout import InstagramLogout
    return InstagramLogout(a.device, _device_id(a))


def _signup(a):
    from taktik.core.social_media.instagram.auth.signup.signup import InstagramSignup
    return InstagramSignup(a.device, _device_id(a))


def _switch(a):
    from taktik.core.social_media.instagram.auth.switch import InstagramSwitchAccount
    return InstagramSwitchAccount(a.device, _device_id(a))


# === Login ===================================================================

@action("account.login")
def login(a, p):
    """Full production login (InstagramLogin.login): fill credentials + submit + detect
    result (success / 2FA / suspicious / error). Params: username, password (required).
    Password is never logged. Run on a TEST account."""
    username = (p.get("username") or "").strip()
    password = p.get("password") or ""
    if not username or not password:
        return {"success": False, "message": "username and password params are required"}
    logger.info(f"account.login: @{username}")
    return _result(_login(a).login(username, password), "login attempted")


@action("account.fill_login_credentials")
def fill_login_credentials(a, p):
    """Fill the login form (the most fragile step: username-vs-password-only, clear/X,
    autofill) without submitting. Params: username, password (required). Be on the login
    screen."""
    username = (p.get("username") or "").strip()
    password = p.get("password") or ""
    if not username or not password:
        return {"success": False, "message": "username and password params are required"}
    ok = _login(a)._fill_credentials(username, password)
    return {"success": bool(ok), "message": f"credentials filled={ok}"}


@action("account.detect_login_screen")
def detect_login_screen(a, p):
    """Detection: are we on the login screen (profile-tile vs form branch)?"""
    v = _login(a)._is_on_login_screen()
    return {"success": True, "found": bool(v), "message": f"on_login_screen={bool(v)}"}


@action("account.detect_login_result")
def detect_login_result(a, p):
    """Detection: classify the current post-submit state (success / 2FA / suspicious /
    error) via the production localized detector."""
    return _result(_login(a)._detect_login_result(), "result detected")


# === Logout ==================================================================

@action("account.logout")
def logout(a, p):
    """Full production logout (InstagramLogout.logout): options menu + scroll-to-find +
    confirm. Run on a TEST account."""
    return _result(_logout(a).logout(), "logout attempted")


@action("account.is_logged_out")
def is_logged_out(a, p):
    """Detection: are we logged out (back on the login screen)?"""
    v = _logout(a)._is_logged_out()
    return {"success": True, "found": bool(v), "message": f"logged_out={bool(v)}"}


# === Switch account (multi-account) =========================================

@action("account.detect_connected_accounts")
def detect_connected_accounts(a, p):
    """Detection: are we already looking at the connected-accounts list (the logged-out account
    picker IG opens on, or an open @username switcher)?"""
    v = _switch(a)._on_landing_account_list()
    return {"success": True, "found": bool(v), "message": f"on_account_list={bool(v)}"}


_NO_ACTIVE_ACCOUNT = {
    "logged_out": "no active account: logged out (account picker on screen)",
    "unreadable": "active account not read (profile not reached, or no @handle on it)",
}


@action("account.detect_active_account")
def detect_active_account(a, p):
    """Read the account currently ACTIVE on the device (@username) from the own profile
    (InstagramSwitchAccount.read_active_account). Not gesture-free: one navigation tap on the
    Profile tab, unless already on it. Non-destructive (no logout). Another app on screen: nothing
    tapped, reason "app_not_foreground", never "logged out"."""
    reading = _switch(a).read_active_account()
    if reading.username:
        message = f"active_account=@{reading.username}"
    elif reading.reason == "app_not_foreground":
        message = f"Instagram not in the foreground ({reading.foreground_package}): nothing read"
    else:
        message = _NO_ACTIVE_ACCOUNT.get(reading.reason, reading.reason)
    return {
        "success": bool(reading.username),
        "found": bool(reading.username),
        "message": message,
        "username": reading.username,
        "details": {"reason": reading.reason, "foreground_package": reading.foreground_package},
    }


@action("account.list_accounts")
def list_accounts(a, p):
    """List the Instagram accounts logged in on the device (InstagramSwitchAccount.list_accounts):
    detect the landing picker or open the profile @username switcher, enumerate the rows. No logout.
    Run on a device with 2+ connected accounts."""
    accounts = _switch(a).list_accounts()
    return {
        "success": True,
        "found": bool(accounts),
        "message": f"{len(accounts)} connected account(s): {accounts}",
        "accounts": accounts,
    }


@action("account.list_saved_accounts")
def list_saved_accounts(a, p):
    """List ALL accounts saved on the device (InstagramSwitchAccount.list_saved_accounts):
    DESTRUCTIVE — when an account is active, logs out to reach the connected-accounts picker (the
    only screen that lists every saved account), enumerates it, and leaves the device on the picker.
    Run on a device with 2+ saved accounts."""
    accounts = _switch(a).list_saved_accounts()
    return {
        "success": True,
        "found": bool(accounts),
        "message": f"{len(accounts)} saved account(s): {accounts}",
        "accounts": accounts,
    }


@action("account.switch_account")
def switch_account(a, p):
    """Switch to another account already logged in on the device (InstagramSwitchAccount.switch_to):
    select it on the picker, or (if an account is active) via the @username switcher / logout
    fallback. Param: username (required). Run on a device with 2+ connected accounts."""
    username = (p.get("username") or "").strip()
    if not username:
        return {"success": False, "message": "username param is required"}
    logger.info(f"account.switch_account: @{username}")
    return _result(_switch(a).switch_to(username), "switch attempted")


# === Signup ==================================================================

@action("account.signup_start")
def signup_start(a, p):
    """Start signup (InstagramSignup.navigate_to_signup): tap create + detect phone/email
    step. Run on a fresh app state."""
    return _result(_signup(a).navigate_to_signup(), "signup started")


@action("account.signup_enter_phone")
def signup_enter_phone(a, p):
    """Signup: type the phone number + Next. Param: phone (required)."""
    phone = (p.get("phone") or "").strip()
    if not phone:
        return {"success": False, "message": "phone param is required"}
    return _result(_signup(a).enter_phone_number(phone), "phone entered")


@action("account.signup_enter_email")
def signup_enter_email(a, p):
    """Signup: type the email + Next (default signup path). Param: email (required)."""
    email = (p.get("email") or "").strip()
    if not email:
        return {"success": False, "message": "email param is required"}
    return _result(_signup(a).enter_email(email), "email entered")
