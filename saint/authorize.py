"""One-time interactive OAuth consent script. Run manually, once per account, from a
machine with a real browser:

    python authorize.py --account personal_google
    python authorize.py --account ogami_google

NEVER run this inside Docker — there is no browser in a headless container. Docker
only ever runs main.py (steady-state operation on already-authorized tokens).
"""

from __future__ import annotations

import argparse
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from accounts.registry import ACCOUNT_NAMES, AccountRegistry
from config import Config
from logging_setup import setup_logging

REDIRECT_PORT = 8080


def _client_config(client_id: str, client_secret: str) -> dict:
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def authorize(account_name: str) -> None:
    config = Config.from_env()
    setup_logging(config.saint_log_level)  # before any OAuth or Google credential handling

    registry = AccountRegistry(config)
    account = registry.get(account_name)

    flow = InstalledAppFlow.from_client_config(
        _client_config(account.client_id, account.client_secret),
        scopes=account.scopes,
    )
    print(f"Opening a browser to authorize '{account_name}'. Sign in with the correct Google account.")
    creds = flow.run_local_server(port=REDIRECT_PORT)

    if any("gmail.send" in scope for scope in creds.scopes or []):
        # Structural guardrail: this should be unreachable since gmail.send is never
        # in ALL_SCOPES, but fail loudly rather than silently accept it if it ever is.
        print("ABORTING: granted scopes include gmail.send. This must never happen.", file=sys.stderr)
        sys.exit(1)

    account.token_path.parent.mkdir(parents=True, exist_ok=True)
    account.token_path.write_text(creds.to_json())

    print(f"\nAuthorized '{account_name}'. Token written to {account.token_path}")
    print("Scopes granted:")
    for scope in creds.scopes or []:
        print(f"  - {scope}")
    print("\nConfirm no send/compose permission appears above.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True, choices=ACCOUNT_NAMES)
    args = parser.parse_args()
    authorize(args.account)
