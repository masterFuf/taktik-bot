"""Account workflows: log in, log out, register, change the app language, switch and list the
accounts of a phone, read a code from Gmail.

One declaration per id of the manifest. The ids of a platform share one launcher
(`run_<platform>_account`) that takes params already read: each id has its own reader
(`*_params_from_payload`), which the CLI handler and the bridge both call. One bridge per platform
runs every flow of it, named by `workflowType`; each prints `status`, `error`, `log` and one
`account_result`, whose fields depend on the flow.
"""

from __future__ import annotations

from typing import Tuple

from .schema import HOST, Event, Field, ListOf, OneOf, Refusal, Shape, WorkflowContract
from .shared import ERROR_EVENT, LOG_EVENT, STATUS_EVENT

_INSTAGRAM = "taktik.core.social_media.instagram.workflows.management.agent_handler"
_TIKTOK = "taktik.core.social_media.tiktok.workflows.management.agent_handler"
_GMAIL = "taktik.core.app.email.gmail.workflows.agent_handler"
_YOUTUBE = "taktik.core.social_media.youtube.workflows.account.agent_handler"

def _device() -> Field:
    return Field("deviceId", "string", "The adb serial of the phone.", required=True, by=HOST)


def _flow(value: str) -> Field:
    return Field("workflowType", OneOf((value,)), "Which flow of the account bridge runs.", required=True)


def _package(module: str, app: str) -> Field:
    return Field("packageName", "string", f"The {app} package to run on (a clone); absent: the default {app}.",
                 aliases=("package_name",), reader=f"{module}:package_name_from_payload")


def _result(flow: str, doc: str, *fields: Field) -> Event:
    return Event("account_result", doc=doc, fields=(
        Field("success", "bool", "The flow did what it was asked."),
        Field("workflow", OneOf((flow,)), "The flow."),
        *fields,
        Field("message", "string", "What happened, for a person."),
    ))


def _error_type(optional: bool = False) -> Field:
    return Field("error_type", "string", "A code for why it failed; null on success.", nullable=True,
                 optional=optional)


def _contract(workflow_id: str, name: str, bridge: str, launcher: str, reader: str, doc: str,
              settings: Tuple[Field, ...], events: Tuple[Event, ...], refusals: Tuple[Refusal, ...] = ()) -> WorkflowContract:
    flow = workflow_id.rsplit(".", 1)[-1]
    return WorkflowContract(
        workflow_id=workflow_id,
        name=name,
        bridge=bridge,
        doc=doc,
        launcher=launcher,
        reader=reader,
        settings=settings,
        bridge_fields=(_device(), _flow(flow)),
        refusals=refusals,
        events=(STATUS_EVENT, ERROR_EVENT, LOG_EVENT, *events),
    )


def _username_password(platform: str) -> Tuple[Field, ...]:
    return (
        Field("username", "string", f"The {platform} account to log in.", required=True, attr="username"),
        Field("password", "string", "Its password.", required=True, attr="password"),
        Field("maxRetries", "int", "Attempts before giving up.", default=3, aliases=("max_retries",),
              attr="max_retries"),
        Field("saveSession", "bool", "Keep the session on the phone.", default=True, aliases=("save_session",),
              attr="save_session"),
    )


def _register() -> Tuple[Field, ...]:
    return (
        Field("method", OneOf(("email", "phone")), "Sign up by email or by phone.", default="email",
              attr="method"),
        Field("email", "string", "The address to sign up with (email method).", attr="email"),
        Field("phone", "string", "The number to sign up with (phone method).", attr="phone"),
    )


_REGISTER_REFUSALS = (
    Refusal("email", when={"method": "email"}, doc="Email sign-up without an address."),
    Refusal("phone", when={"method": "phone"}, doc="Phone sign-up without a number."),
)
_LOGIN_REFUSALS = (
    Refusal("username", doc="No account to log in."),
    Refusal("password", doc="No password."),
)

# ------------------------------------------------------------------------------------ Instagram

_IG_BRIDGE = "account_bridge"
_IG_LAUNCHER = f"{_INSTAGRAM}:run_instagram_account"
_IG_PACKAGE = _package(_INSTAGRAM, "Instagram")

#: Narration of the flows that walk the account picker (`on_active_account`, `on_step`).
_ACTIVE_ACCOUNT = Event("active_account_detected", doc="The account the phone shows as active.", fields=(
    Field("username", "string", "Its handle."),
    Field("workflow", OneOf(("switch_account", "list_accounts", "list_saved_accounts")), "The flow."),
))
_ACCOUNT_STEP = Event("account_step", doc="One step on the phone, for the Agent panel.", fields=(
    Field("step", "string", "navigate_profile, active_account, logout, enumerate, select, relogin, switched."),
    Field("workflow", OneOf(("switch_account", "list_accounts", "list_saved_accounts")), "The flow."),
    Field("username", "string", "The account the step is about.", optional=True),
    Field("accounts", ListOf("string"), "The accounts the picker shows (enumerate).", optional=True),
))
_ACCOUNTS_DETECTED = Event("accounts_detected", doc="The accounts seen on the phone.", fields=(
    Field("accounts", ListOf("string"), "Their handles."),
))
_SAVED_ACCOUNTS_DETECTED = Event("saved_accounts_detected",
                                 doc="Every account the picker holds: the phone's saved accounts.", fields=(
    Field("accounts", ListOf("string"), "Their handles."),
))
_DETECTED = Field("detected_accounts", ListOf("string"), "The accounts seen on the picker.")

INSTAGRAM_ACCOUNT_LOGIN = _contract(
    "instagram.account.login", "InstagramAccountLogin", _IG_BRIDGE, _IG_LAUNCHER,
    f"{_INSTAGRAM}:login_params_from_payload",
    "Log an Instagram account in.",
    settings=(
        *_username_password("Instagram"),
        Field("useSavedSession", "bool", "Reuse a session saved on the phone when there is one.", default=True,
              aliases=("use_saved_session",), attr="use_saved_session"),
        Field("saveLoginInfoInstagram", "bool", "Answer yes when Instagram offers to save the login.",
              default=False, aliases=("save_login_info_instagram",), attr="save_login_info_instagram"),
        _IG_PACKAGE,
    ),
    refusals=_LOGIN_REFUSALS,
    events=(_result("login", "The login is over.",
                    Field("username", "string", "The account."), _error_type()),),
)

INSTAGRAM_ACCOUNT_REGISTER = _contract(
    "instagram.account.register", "InstagramAccountRegister", _IG_BRIDGE, _IG_LAUNCHER,
    f"{_INSTAGRAM}:register_params_from_payload",
    "Create an Instagram account.",
    settings=(*_register(), _IG_PACKAGE),
    refusals=_REGISTER_REFUSALS,
    events=(_result("register", "The sign-up is over.",
                    Field("step", "string", "The last step reached."), _error_type()),),
)

INSTAGRAM_ACCOUNT_LOGOUT = _contract(
    "instagram.account.logout", "InstagramAccountLogout", _IG_BRIDGE, _IG_LAUNCHER,
    f"{_INSTAGRAM}:no_params_from_payload",
    "Log the active Instagram account out.",
    settings=(_IG_PACKAGE,),
    events=(_result("logout", "The logout is over.", _error_type()),),
)

INSTAGRAM_ACCOUNT_CHANGE_LANGUAGE = _contract(
    "instagram.account.change_language", "InstagramAccountChangeLanguage", _IG_BRIDGE, _IG_LAUNCHER,
    f"{_INSTAGRAM}:change_language_params_from_payload",
    "Set the Instagram app language, then restart Instagram.",
    settings=(
        Field("language", "string", "The language code (`APP_LANGUAGE_NATIVE_NAMES`: en, en-GB, fr-FR, fr-CA).",
              required=True, attr="language"),
        _IG_PACKAGE,
    ),
    refusals=(Refusal("language", doc="No language."),),
    events=(
        Event("change_language_step", doc="One step on the phone, for the Agent panel.", fields=(
            Field("step", "string", "validate, open_profile, open_options, open_language_settings, open_picker, "
                  "select_language, restart_app, done."),
            Field("step_status", OneOf(("running", "done", "failed")), "Where the step is."),
            Field("message", "string", "What happens, for a person."),
            Field("language", "string", "The language code (select_language, done).", optional=True),
            Field("native_name", "string", "The language as the picker writes it.", optional=True),
        )),
        _result("change_language", "The language change is over.",
                Field("language", "string", "The language code asked."),
                Field("native_name", "string", "The language as the picker writes it.", nullable=True),
                _error_type(),
                Field("app_restarted", "bool", "Instagram came back after the restart; false, some screens keep "
                      "the old language until it starts again.", optional=True)),
    ),
)

INSTAGRAM_ACCOUNT_SWITCH = _contract(
    "instagram.account.switch_account", "InstagramAccountSwitch", _IG_BRIDGE, _IG_LAUNCHER,
    f"{_INSTAGRAM}:switch_account_params_from_payload",
    "Switch to an account already logged in on the phone.",
    settings=(
        Field("targetUsername", "string", "The account to switch to, without @.", required=True,
              aliases=("target_username",), attr="target_username"),
        _IG_PACKAGE,
    ),
    refusals=(Refusal("targetUsername", doc="No account to switch to."),),
    events=(
        _ACTIVE_ACCOUNT, _ACCOUNT_STEP, _ACCOUNTS_DETECTED, _SAVED_ACCOUNTS_DETECTED,
        _result("switch_account", "The switch is over.",
                _error_type(),
                Field("switched_to", "string", "The account now active.", nullable=True),
                Field("relogin_required", "bool", "The account is known but its session is not saved: log in."),
                _DETECTED),
    ),
)

INSTAGRAM_ACCOUNT_LIST = _contract(
    "instagram.account.list_accounts", "InstagramAccountList", _IG_BRIDGE, _IG_LAUNCHER,
    f"{_INSTAGRAM}:no_params_from_payload",
    "List the accounts logged in on the phone, without logging out.",
    settings=(_IG_PACKAGE,),
    events=(
        _ACTIVE_ACCOUNT, _ACCOUNT_STEP, _ACCOUNTS_DETECTED,
        _result("list_accounts", "The list is read.", _DETECTED),
    ),
)

INSTAGRAM_ACCOUNT_LIST_SAVED = _contract(
    "instagram.account.list_saved_accounts", "InstagramAccountListSaved", _IG_BRIDGE, _IG_LAUNCHER,
    f"{_INSTAGRAM}:no_params_from_payload",
    "List every account saved on the phone: logs out to reach the account picker.",
    settings=(_IG_PACKAGE,),
    events=(
        _ACTIVE_ACCOUNT, _ACCOUNT_STEP, _ACCOUNTS_DETECTED, _SAVED_ACCOUNTS_DETECTED,
        _result("list_saved_accounts", "The list is read.", _DETECTED),
    ),
)

# --------------------------------------------------------------------------------------- TikTok

_TT_BRIDGE = "tiktok_account_bridge"
_TT_LAUNCHER = f"{_TIKTOK}:run_tiktok_account"
_TT_PACKAGE = _package(_TIKTOK, "TikTok")

TIKTOK_ACCOUNT_LOGIN = _contract(
    "tiktok.account.login", "TikTokAccountLogin", _TT_BRIDGE, _TT_LAUNCHER,
    f"{_TIKTOK}:login_params_from_payload",
    "Log a TikTok account in.",
    settings=(*_username_password("TikTok"), _TT_PACKAGE),
    refusals=_LOGIN_REFUSALS,
    events=(_result("login", "The login is over.",
                    Field("username", "string", "The account."), _error_type()),),
)

TIKTOK_ACCOUNT_REGISTER = _contract(
    "tiktok.account.register", "TikTokAccountRegister", _TT_BRIDGE, _TT_LAUNCHER,
    f"{_TIKTOK}:register_params_from_payload",
    "Create a TikTok account.",
    settings=(
        *_register(),
        Field("phoneCountry", "string", "The country of the number (phone method).", aliases=("phone_country",),
              attr="phone_country"),
        Field("birthYear", "int", "Birth year entered.", default=1995, aliases=("birth_year",), attr="birth_year"),
        Field("birthMonth", "int", "Birth month entered.", default=6, aliases=("birth_month",), attr="birth_month"),
        Field("birthDay", "int", "Birth day entered.", default=15, aliases=("birth_day",), attr="birth_day"),
        Field("gmailPassword", "string", "The Gmail password, to read the code TikTok mails (email method).",
              aliases=("gmail_password",), attr="gmail_password"),
        Field("tiktokPassword", "string", "The password of the new account.", aliases=("tiktok_password",),
              attr="tiktok_password"),
        Field("nickname", "string", "The display name of the new account.", attr="nickname"),
        _TT_PACKAGE,
    ),
    refusals=_REGISTER_REFUSALS,
    events=(_result("register", "The sign-up is over.",
                    Field("step", "string", "The last step reached."), _error_type()),),
)

TIKTOK_ACCOUNT_LOGOUT = _contract(
    "tiktok.account.logout", "TikTokAccountLogout", _TT_BRIDGE, _TT_LAUNCHER,
    f"{_TIKTOK}:no_params_from_payload",
    "Log the active TikTok account out.",
    settings=(_TT_PACKAGE,),
    events=(_result("logout", "The logout is over.", _error_type()),),
)

TIKTOK_ACCOUNT_CHANGE_LANGUAGE = _contract(
    "tiktok.account.change_language", "TikTokAccountChangeLanguage", _TT_BRIDGE, _TT_LAUNCHER,
    f"{_TIKTOK}:change_language_params_from_payload",
    "Set the TikTok app language, and prove it changed.",
    settings=(
        Field("targetLanguage", "string", "The language code (`APP_LANGUAGE_NATIVE_NAMES`: en, en-GB, en-US, fr, "
              "fr-FR, fr-CA).", required=True, aliases=("target_language", "language"), attr="target_language"),
        _TT_PACKAGE,
    ),
    refusals=(Refusal("targetLanguage", doc="No language: refused rather than defaulted."),),
    events=(_result("change_language", "The language change is over.",
                    _error_type(),
                    Field("language_before", "string", "The language read before.", nullable=True),
                    Field("language_after", "string", "The language read after.", nullable=True),
                    Field("already_set", "bool", "The language was already the one asked.")),),
)

# ---------------------------------------------------------------------------------------- Gmail

_GM_BRIDGE = "gmail_account_bridge"
_GM_LAUNCHER = f"{_GMAIL}:run_gmail_account"
_EMAIL = Field("email", "string", "The Google account.", required=True, attr="email")
_EMAIL_REFUSAL = Refusal("email", doc="No Google account.")

GMAIL_ACCOUNT_ON_PHONE = Shape(
    name="GmailAccountOnPhone",
    doc="A Google account the Gmail account switcher lists.",
    fields=(
        Field("name", "string", "Its display name.", nullable=True),
        Field("email", "string", "Its address."),
        Field("is_active", "bool", "The account Gmail shows."),
    ),
)

GMAIL_ACCOUNT_LOGIN = _contract(
    "gmail.account.login", "GmailAccountLogin", _GM_BRIDGE, _GM_LAUNCHER,
    f"{_GMAIL}:login_params_from_payload",
    "Add a Google account to the phone; kept in the base on success.",
    settings=(_EMAIL, Field("password", "string", "Its password.", required=True, attr="password")),
    refusals=(_EMAIL_REFUSAL, Refusal("password", doc="No password.")),
    events=(_result("login", "The flow is over.", Field("email", "string", "The account."), _error_type()),),
)

GMAIL_ACCOUNT_LOGOUT = _contract(
    "gmail.account.logout", "GmailAccountLogout", _GM_BRIDGE, _GM_LAUNCHER,
    f"{_GMAIL}:logout_params_from_payload",
    "Remove a Google account from the phone; forgotten by the base on success.",
    settings=(_EMAIL,),
    refusals=(_EMAIL_REFUSAL,),
    events=(_result("logout", "The flow is over.", Field("email", "string", "The account."), _error_type()),),
)

GMAIL_ACCOUNT_READ_OTP = _contract(
    "gmail.account.read_otp", "GmailAccountReadOtp", _GM_BRIDGE, _GM_LAUNCHER,
    f"{_GMAIL}:read_otp_params_from_payload",
    "Read the latest verification code of an inbox.",
    settings=(
        _EMAIL,
        Field("senderFilter", "string", "Only a mail from this sender.", aliases=("sender_filter",),
              attr="sender_filter"),
        Field("subjectFilter", "string", "Only a mail with this in its subject.", aliases=("subject_filter",),
              attr="subject_filter"),
        Field("timeout", "int", "Seconds to wait for the mail; 0 waits the default.", default=120, attr="timeout"),
    ),
    refusals=(_EMAIL_REFUSAL,),
    events=(_result("read_otp", "The flow is over.",
                    Field("email", "string", "The account."), _error_type(),
                    Field("code", "string", "The code read.", nullable=True)),),
)

GMAIL_ACCOUNT_SCAN = _contract(
    "gmail.account.scan_accounts", "GmailAccountScan", _GM_BRIDGE, _GM_LAUNCHER,
    f"{_GMAIL}:scan_accounts_params_from_payload",
    "List the Google accounts of the phone; each is kept in the base.",
    settings=(),
    events=(_result("scan_accounts", "The flow is over.",
                    Field("accounts", ListOf(GMAIL_ACCOUNT_ON_PHONE), "The accounts found."), _error_type()),),
)

# -------------------------------------------------------------------------------------- YouTube

_YT_BRIDGE = "youtube_account_bridge"
_YT_LAUNCHER = f"{_YOUTUBE}:run_youtube_account"

YOUTUBE_ACCOUNT_LOGIN = _contract(
    "youtube.account.login", "YouTubeAccountLogin", _YT_BRIDGE, _YT_LAUNCHER,
    f"{_YOUTUBE}:login_params_from_payload",
    "Sign YouTube in with a Google account, added to the phone first when needed.",
    settings=(
        _EMAIL,
        Field("password", "string", "Its password, when the account is not on the phone yet.", default="",
              attr="password"),
    ),
    refusals=(_EMAIL_REFUSAL,),
    events=(_result("login", "The sign-in succeeded (a failure is an `error` line).",
                    Field("email", "string", "The account.")),),
)

YOUTUBE_ACCOUNT_LOGOUT = _contract(
    "youtube.account.logout", "YouTubeAccountLogout", _YT_BRIDGE, _YT_LAUNCHER,
    f"{_YOUTUBE}:logout_params_from_payload",
    "Sign YouTube out.",
    settings=(Field("email", "string", "The account to sign out; empty, the one signed in.", default="",
                    attr="email"),),
    events=(_result("logout", "The sign-out succeeded (a failure is an `error` line).",
                    Field("email", "string", "The account.")),),
)

CONTRACTS = (
    INSTAGRAM_ACCOUNT_LOGIN,
    INSTAGRAM_ACCOUNT_REGISTER,
    INSTAGRAM_ACCOUNT_LOGOUT,
    INSTAGRAM_ACCOUNT_CHANGE_LANGUAGE,
    INSTAGRAM_ACCOUNT_SWITCH,
    INSTAGRAM_ACCOUNT_LIST,
    INSTAGRAM_ACCOUNT_LIST_SAVED,
    TIKTOK_ACCOUNT_LOGIN,
    TIKTOK_ACCOUNT_REGISTER,
    TIKTOK_ACCOUNT_LOGOUT,
    TIKTOK_ACCOUNT_CHANGE_LANGUAGE,
    GMAIL_ACCOUNT_LOGIN,
    GMAIL_ACCOUNT_LOGOUT,
    GMAIL_ACCOUNT_READ_OTP,
    GMAIL_ACCOUNT_SCAN,
    YOUTUBE_ACCOUNT_LOGIN,
    YOUTUBE_ACCOUNT_LOGOUT,
)

__all__ = [
    "CONTRACTS",
    "GMAIL_ACCOUNT_LOGIN",
    "GMAIL_ACCOUNT_LOGOUT",
    "GMAIL_ACCOUNT_READ_OTP",
    "GMAIL_ACCOUNT_SCAN",
    "INSTAGRAM_ACCOUNT_CHANGE_LANGUAGE",
    "INSTAGRAM_ACCOUNT_LIST",
    "INSTAGRAM_ACCOUNT_LIST_SAVED",
    "INSTAGRAM_ACCOUNT_LOGIN",
    "INSTAGRAM_ACCOUNT_LOGOUT",
    "INSTAGRAM_ACCOUNT_REGISTER",
    "INSTAGRAM_ACCOUNT_SWITCH",
    "LOG_EVENT",
    "TIKTOK_ACCOUNT_CHANGE_LANGUAGE",
    "TIKTOK_ACCOUNT_LOGIN",
    "TIKTOK_ACCOUNT_LOGOUT",
    "TIKTOK_ACCOUNT_REGISTER",
    "YOUTUBE_ACCOUNT_LOGIN",
    "YOUTUBE_ACCOUNT_LOGOUT",
]
