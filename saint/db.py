"""Operational state: the consequential-action approval queue and its audit log.

This is NOT "memory" in the product sense (see data/memory/ for that). It is the
load-bearing mechanism for security-boundaries.md's "no silent side effects" rule:
every consequential tool call becomes a row here before it is ever executed, and
every state transition is mirrored into audit_log.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
        -- pending | approved | rejected | executed | failed | expired
    tool_name TEXT NOT NULL,
    account TEXT,
    tool_args_json TEXT NOT NULL,
    action_class TEXT NOT NULL,
    requested_by_run_id TEXT,
    telegram_message_id INTEGER,
    telegram_chat_id INTEGER,
    result_json TEXT,
    rejected_reason TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    event TEXT NOT NULL,
    approval_id INTEGER,
    detail_json TEXT
);

CREATE TABLE IF NOT EXISTS model_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    date TEXT NOT NULL,
    tier TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL
);
"""

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
EXECUTED = "executed"
FAILED = "failed"
EXPIRED = "expired"

TERMINAL_STATUSES = {REJECTED, EXECUTED, FAILED, EXPIRED}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Approval:
    id: int
    created_at: str
    updated_at: str
    expires_at: str
    status: str
    tool_name: str
    account: Optional[str]
    tool_args: dict
    action_class: str
    requested_by_run_id: Optional[str]
    telegram_message_id: Optional[int]
    telegram_chat_id: Optional[int]
    result: Optional[dict]
    rejected_reason: Optional[str]

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Approval":
        return cls(
            id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            status=row["status"],
            tool_name=row["tool_name"],
            account=row["account"],
            tool_args=json.loads(row["tool_args_json"]),
            action_class=row["action_class"],
            requested_by_run_id=row["requested_by_run_id"],
            telegram_message_id=row["telegram_message_id"],
            telegram_chat_id=row["telegram_chat_id"],
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            rejected_reason=row["rejected_reason"],
        )


class Database:
    """Opens a fresh SQLite connection per call — simplest safe option at single-user,
    low-volume scale; avoids any cross-thread/cross-loop connection-sharing footguns
    (APScheduler's default executor can run blocking jobs on a thread pool)."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # --- approvals ---

    def create_approval(
        self,
        *,
        tool_name: str,
        tool_args: dict,
        action_class: str,
        account: Optional[str] = None,
        requested_by_run_id: Optional[str] = None,
        ttl_hours: int = 24,
    ) -> int:
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(hours=ttl_hours)).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO approvals
                   (created_at, updated_at, expires_at, status, tool_name, account,
                    tool_args_json, action_class, requested_by_run_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    now.isoformat(),
                    now.isoformat(),
                    expires_at,
                    PENDING,
                    tool_name,
                    account,
                    json.dumps(tool_args),
                    action_class,
                    requested_by_run_id,
                ),
            )
            approval_id = cur.lastrowid
        self.log_audit(
            "approval.created",
            approval_id=approval_id,
            detail={"tool_name": tool_name, "account": account, "action_class": action_class},
        )
        return approval_id

    def get_approval(self, approval_id: int) -> Optional[Approval]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        return Approval.from_row(row) if row else None

    def set_telegram_message(self, approval_id: int, chat_id: int, message_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE approvals SET telegram_chat_id = ?, telegram_message_id = ?, updated_at = ? WHERE id = ?",
                (chat_id, message_id, _now(), approval_id),
            )

    def update_status(
        self,
        approval_id: int,
        status: str,
        *,
        result: Optional[dict] = None,
        rejected_reason: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE approvals
                   SET status = ?, updated_at = ?, result_json = ?, rejected_reason = ?
                   WHERE id = ?""",
                (
                    status,
                    _now(),
                    json.dumps(result) if result is not None else None,
                    rejected_reason,
                    approval_id,
                ),
            )
        self.log_audit(
            f"approval.{status}",
            approval_id=approval_id,
            detail={"result": result, "rejected_reason": rejected_reason},
        )

    def list_pending(self) -> list[Approval]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM approvals WHERE status = ? ORDER BY created_at", (PENDING,)
            ).fetchall()
        return [Approval.from_row(r) for r in rows]

    def expire_stale(self) -> list[int]:
        """Fail-closed reconciliation: mark pending rows past expires_at as expired.
        Call on startup and periodically; never silently execute a stale approval."""
        now = _now()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM approvals WHERE status = ? AND expires_at < ?", (PENDING, now)
            ).fetchall()
            ids = [r["id"] for r in rows]
            if ids:
                conn.executemany(
                    "UPDATE approvals SET status = ?, updated_at = ? WHERE id = ?",
                    [(EXPIRED, now, i) for i in ids],
                )
        for i in ids:
            self.log_audit("approval.expired", approval_id=i)
        return ids

    # --- model usage / budget governor ---

    def record_usage(
        self, *, tier: str, model: str, input_tokens: int, output_tokens: int, cost_usd: float
    ) -> None:
        now = datetime.now(timezone.utc)
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO model_usage (ts, date, tier, model, input_tokens, output_tokens, cost_usd)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (now.isoformat(), now.date().isoformat(), tier, model, input_tokens, output_tokens, cost_usd),
            )

    def get_daily_spend(self, on_date: Optional[str] = None) -> float:
        on_date = on_date or datetime.now(timezone.utc).date().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM model_usage WHERE date = ?", (on_date,)
            ).fetchone()
        return row["total"]

    # --- audit log ---

    def log_audit(self, event: str, *, approval_id: Optional[int] = None, detail: Optional[dict] = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_log (ts, event, approval_id, detail_json) VALUES (?, ?, ?, ?)",
                (_now(), event, approval_id, json.dumps(detail) if detail is not None else None),
            )


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "smoke.db")
        aid = db.create_approval(
            tool_name="delete_calendar_event",
            tool_args={"event_id": "abc123"},
            action_class="Destructive",
            account="ogami_google",
        )
        print("created approval", aid, db.get_approval(aid))
        db.set_telegram_message(aid, chat_id=111, message_id=222)
        db.update_status(aid, APPROVED)
        db.update_status(aid, EXECUTED, result={"deleted": True})
        print("final", db.get_approval(aid))
        print("pending now:", db.list_pending())
        print("smoke test OK")
