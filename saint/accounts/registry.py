"""Maps account names ("personal_google", "ogami_google") to configured GoogleAccount
instances. Built once in main.py and threaded down into tools and agent.py.

Scopes are hardcoded here, not read from .env — making them a runtime knob would let
a future edit silently request a broader scope (e.g. gmail.send). Changing what Saint
is allowed to touch requires a code change and review, not a config tweak.
"""

from __future__ import annotations

from config import Config

from accounts.google_account import GoogleAccount

# gmail.send is deliberately never included. Saint cannot send email — not gated,
# structurally absent.
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TASKS_SCOPES = ["https://www.googleapis.com/auth/tasks"]

ALL_SCOPES = GMAIL_SCOPES + DRIVE_SCOPES + CALENDAR_SCOPES + TASKS_SCOPES

PERSONAL_GOOGLE = "personal_google"
OGAMI_GOOGLE = "ogami_google"
ACCOUNT_NAMES = [PERSONAL_GOOGLE, OGAMI_GOOGLE]


class AccountRegistry:
    def __init__(self, config: Config):
        self._accounts: dict[str, GoogleAccount] = {
            PERSONAL_GOOGLE: GoogleAccount(
                name=PERSONAL_GOOGLE,
                client_id=config.google_personal_client_id,
                client_secret=config.google_personal_client_secret,
                token_path=config.google_personal_token_path,
                scopes=ALL_SCOPES,
            ),
            OGAMI_GOOGLE: GoogleAccount(
                name=OGAMI_GOOGLE,
                client_id=config.google_ogami_client_id,
                client_secret=config.google_ogami_client_secret,
                token_path=config.google_ogami_token_path,
                scopes=ALL_SCOPES,
            ),
        }

    def get(self, account_name: str) -> GoogleAccount:
        try:
            return self._accounts[account_name]
        except KeyError:
            raise ValueError(
                f"Unknown account '{account_name}'. Valid accounts: {list(self._accounts)}"
            ) from None

    def all_accounts(self) -> dict[str, GoogleAccount]:
        return dict(self._accounts)
