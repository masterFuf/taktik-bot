"""Account-lifecycle actions for TikTok compat diagnostics (Cartography Lab).

Login / logout / signup via the production TikTok workflows built on the warm Lab device.
AUTH screens — run on a TEST account. Credentials/identity are params for the test and are
never logged.
"""

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action


def _device_id(a):
    return getattr(a.device, "device_id", None) or "lab"


def _wrap(result, fallback):
    if isinstance(result, dict):
        return {"success": bool(result.get("success", True)),
                "message": result.get("message") or fallback, "details": result}
    return {"success": bool(result), "message": fallback, "details": {"value": result}}


@action("tt.account.login")
def login(a, p):
    """Full production TikTok login (TikTokLoginWorkflow.execute). Params: username,
    password (required). Password never logged. Run on a TEST account."""
    username = (p.get("username") or "").strip()
    password = p.get("password") or ""
    if not username or not password:
        return {"success": False, "message": "username and password params are required"}
    from taktik.core.social_media.tiktok.workflows.management.login.login_workflow import TikTokLoginWorkflow
    logger.info(f"tt.account.login: @{username}")
    return _wrap(TikTokLoginWorkflow(a.device, _device_id(a)).execute(username, password), "login attempted")


@action("tt.account.logout")
def logout(a, p):
    """Full production TikTok logout (TikTokLogoutWorkflow.execute: settings + scroll-to +
    confirm). Run on a TEST account."""
    from taktik.core.social_media.tiktok.workflows.management.logout.logout_workflow import TikTokLogoutWorkflow
    return _wrap(TikTokLogoutWorkflow(a.device, _device_id(a)).execute(), "logout attempted")


@action("tt.account.signup")
def signup(a, p):
    """Full production TikTok signup (TikTokSignupWorkflow.execute). Params: method
    (email/phone, default email), email, phone, birth_year/birth_month/birth_day. Run on a
    fresh app state."""
    from taktik.core.social_media.tiktok.workflows.management.signup.signup_workflow import TikTokSignupWorkflow

    def _int(key, default):
        try:
            return int(p.get(key) or default)
        except (TypeError, ValueError):
            return default

    wf = TikTokSignupWorkflow(a.device, _device_id(a))
    return _wrap(wf.execute(
        method=(p.get("method") or "email").strip(),
        email=(p.get("email") or None),
        phone=(p.get("phone") or None),
        birth_year=_int("birth_year", 1995),
        birth_month=_int("birth_month", 6),
        birth_day=_int("birth_day", 15),
    ), "signup attempted")


@action("tt.account.signup_detect_screen")
def signup_detect_screen(a, p):
    """Detection: classify the current signup screen (drives the whole signup state machine)."""
    from taktik.core.social_media.tiktok.workflows.management.signup.signup_workflow import TikTokSignupWorkflow
    screen = TikTokSignupWorkflow(a.device, _device_id(a))._detect_screen()
    logger.info(f"tt.account.signup_detect_screen: {screen}")
    return {"success": bool(screen), "message": f"screen={screen}", "details": {"screen": screen}}


@action("tt.account.signup_fill_birthday")
def signup_fill_birthday(a, p):
    """Signup: fill the birthday (the most intricate gesture — SeekBar swipe-until-target).
    Params: birth_day, birth_month, birth_year (defaults 15/6/1995)."""
    from taktik.core.social_media.tiktok.workflows.management.signup.signup_workflow import TikTokSignupWorkflow

    def _int(key, default):
        try:
            return int(p.get(key) or default)
        except (TypeError, ValueError):
            return default

    wf = TikTokSignupWorkflow(a.device, _device_id(a))
    return _wrap(wf._fill_birthday(_int("birth_day", 15), _int("birth_month", 6), _int("birth_year", 1995)),
                 "birthday filled")
