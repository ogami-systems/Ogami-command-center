"""Typed configuration loaded from .env. Fails loudly (all at once) on missing required vars."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

REQUIRED_VARS = [
    # Only what Saint's Telegram interface itself needs to boot at all. Everything
    # else (Anthropic key, Google client credentials) is validated at first real
    # use instead — a Claude call or a Google API call raises its own clear error
    # — so connectors can be brought online one at a time (Telegram, then each
    # Google account, then Docker) without an all-or-nothing wall at startup.
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_OWNER_ID",
]

SECRET_FIELDS = {
    "anthropic_api_key",
    "telegram_bot_token",
    "google_personal_client_secret",
    "google_ogami_client_secret",
    "google_imago_client_secret",
    "spotify_client_secret",
}


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _resolve_path(raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else (BASE_DIR / p)


@dataclass
class Config:
    anthropic_api_key: str
    telegram_bot_token: str
    telegram_owner_id: int

    google_personal_client_id: str
    google_personal_client_secret: str
    google_personal_token_path: Path

    google_ogami_client_id: str
    google_ogami_client_secret: str
    google_ogami_token_path: Path

    google_imago_client_id: str
    google_imago_client_secret: str
    google_imago_token_path: Path

    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    model_daily_budget_usd: float = 5.00
    max_escalations_per_run: int = 2

    saint_env: str = "development"
    saint_db_path: Path = field(default_factory=lambda: BASE_DIR / "data" / "saint.db")
    saint_log_level: str = "INFO"
    saint_timezone: str = "UTC"

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Config":
        load_dotenv(dotenv_path=env_file or (BASE_DIR / ".env"))

        missing = [name for name in REQUIRED_VARS if not os.environ.get(name)]
        if missing:
            raise ConfigError(
                "Missing required environment variable(s): "
                + ", ".join(missing)
                + ". Copy saint/.env.example to saint/.env and fill these in."
            )

        try:
            owner_id = int(os.environ["TELEGRAM_OWNER_ID"])
        except ValueError as exc:
            raise ConfigError("TELEGRAM_OWNER_ID must be a numeric Telegram user ID.") from exc

        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            telegram_owner_id=owner_id,
            google_personal_client_id=os.environ.get("GOOGLE_PERSONAL_CLIENT_ID", ""),
            google_personal_client_secret=os.environ.get("GOOGLE_PERSONAL_CLIENT_SECRET", ""),
            google_personal_token_path=_resolve_path(
                os.environ.get("GOOGLE_PERSONAL_TOKEN_PATH", "secrets/personal_google_token.json")
            ),
            google_ogami_client_id=os.environ.get("GOOGLE_OGAMI_CLIENT_ID", ""),
            google_ogami_client_secret=os.environ.get("GOOGLE_OGAMI_CLIENT_SECRET", ""),
            google_ogami_token_path=_resolve_path(
                os.environ.get("GOOGLE_OGAMI_TOKEN_PATH", "secrets/ogami_google_token.json")
            ),
            google_imago_client_id=os.environ.get("GOOGLE_IMAGO_CLIENT_ID", ""),
            google_imago_client_secret=os.environ.get("GOOGLE_IMAGO_CLIENT_SECRET", ""),
            google_imago_token_path=_resolve_path(
                os.environ.get("GOOGLE_IMAGO_TOKEN_PATH", "secrets/imago_google_token.json")
            ),
            spotify_client_id=os.environ.get("SPOTIFY_CLIENT_ID", ""),
            spotify_client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET", ""),
            model_daily_budget_usd=float(os.environ.get("MODEL_DAILY_BUDGET_USD", "5.00")),
            max_escalations_per_run=int(os.environ.get("MAX_ESCALATIONS_PER_RUN", "2")),
            saint_env=os.environ.get("SAINT_ENV", "development"),
            saint_db_path=_resolve_path(os.environ.get("SAINT_DB_PATH", "data/saint.db")),
            saint_log_level=os.environ.get("SAINT_LOG_LEVEL", "INFO"),
            saint_timezone=os.environ.get("SAINT_TIMEZONE", "UTC"),
        )

    def __repr__(self) -> str:
        parts = []
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name in SECRET_FIELDS and value:
                value = value[:4] + "…" + f"({len(value)} chars)"
            parts.append(f"{f.name}={value!r}")
        return "Config(" + ", ".join(parts) + ")"


if __name__ == "__main__":
    cfg = Config.from_env()
    print(cfg)
