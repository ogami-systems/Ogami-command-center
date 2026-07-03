"""One Google account's lazy auth + cached API service clients.

Constructing a GoogleAccount never touches the network or disk beyond storing
config. Auth happens on first get_*_service() call and is cached per service.
This process NEVER opens a browser — that is authorize.py's exclusive job, run
manually, once per account, always outside Docker.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class AuthRequiredError(RuntimeError):
    """Raised when an account has no usable token. The fix is always the same:
    run `python authorize.py --account <name>` interactively, with a browser."""


class GoogleAccount:
    def __init__(self, name: str, client_id: str, client_secret: str, token_path: Path, scopes: list[str]):
        self.name = name
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_path = Path(token_path)
        self.scopes = scopes
        self._credentials: Optional[Credentials] = None
        self._services: dict[tuple[str, str], object] = {}

    def _load_credentials(self) -> Credentials:
        if self._credentials is not None and self._credentials.valid:
            return self._credentials

        if not self.token_path.exists():
            raise AuthRequiredError(
                f"No token found for '{self.name}' at {self.token_path}. "
                f"Run: python authorize.py --account {self.name}"
            )

        creds = Credentials.from_authorized_user_file(str(self.token_path), self.scopes)

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as exc:
                raise AuthRequiredError(
                    f"Token for '{self.name}' could not be refreshed (likely revoked). "
                    f"Run: python authorize.py --account {self.name}"
                ) from exc
            self.token_path.write_text(creds.to_json())

        if not creds or not creds.valid:
            raise AuthRequiredError(
                f"Token for '{self.name}' is invalid. Run: python authorize.py --account {self.name}"
            )

        self._credentials = creds
        return creds

    def _get_service(self, service_name: str, version: str):
        key = (service_name, version)
        if key not in self._services:
            creds = self._load_credentials()
            self._services[key] = build(service_name, version, credentials=creds, cache_discovery=False)
        return self._services[key]

    def get_gmail_service(self):
        return self._get_service("gmail", "v1")

    def get_drive_service(self):
        return self._get_service("drive", "v3")

    def get_docs_service(self):
        return self._get_service("docs", "v1")

    def get_sheets_service(self):
        return self._get_service("sheets", "v4")

    def get_calendar_service(self):
        return self._get_service("calendar", "v3")

    def get_tasks_service(self):
        return self._get_service("tasks", "v1")

    def __repr__(self) -> str:
        return f"GoogleAccount(name={self.name!r}, token_path={self.token_path})"
