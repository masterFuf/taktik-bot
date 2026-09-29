"""Gmail workflow owners."""

from taktik.core.social_media.gmail.workflows.agent_handler import (
    GMAIL_ACCOUNT_LOGIN_WORKFLOW_ID,
    GMAIL_ACCOUNT_LOGOUT_WORKFLOW_ID,
    GMAIL_ACCOUNT_READ_OTP_WORKFLOW_ID,
    GMAIL_ACCOUNT_SCAN_ACCOUNTS_WORKFLOW_ID,
    GMAIL_ACCOUNT_WORKFLOW_IDS,
    build_gmail_account_handler,
    register_gmail_account_handlers,
)
from taktik.core.social_media.gmail.workflows.account import GmailWorkflow

__all__ = [
    "GMAIL_ACCOUNT_LOGIN_WORKFLOW_ID",
    "GMAIL_ACCOUNT_LOGOUT_WORKFLOW_ID",
    "GMAIL_ACCOUNT_READ_OTP_WORKFLOW_ID",
    "GMAIL_ACCOUNT_SCAN_ACCOUNTS_WORKFLOW_ID",
    "GMAIL_ACCOUNT_WORKFLOW_IDS",
    "GmailWorkflow",
    "build_gmail_account_handler",
    "register_gmail_account_handlers",
]
