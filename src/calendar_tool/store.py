"""Almacén SQLite compartido: lo escribe `calendar-tool sync` y lo leen `calendar-watch`
(y, más adelante, el dashboard). Las fechas se guardan en UTC con formato fijo para que
la comparación de texto respete el orden cronológico.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .models import CalendarEvent

DEFAULT_DB = Path("~/.local/share/calendar-tool/calendar.db").expanduser()

_TS = "%Y-%m-%dT%H:%M:%S.%fZ"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    account TEXT NOT NULL,
    calendar_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    ical_uid TEXT NOT NULL,
    title TEXT NOT NULL,
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    all_day INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    location TEXT NOT NULL,
    hangout_link TEXT NOT NULL,
    attendees TEXT NOT NULL,
    response_status TEXT NOT NULL,
    transparency TEXT NOT NULL,
    conference_link TEXT NOT NULL,
    updated TEXT NOT NULL,
    PRIMARY KEY (account, calendar_id, event_id)
);
CREATE INDEX IF NOT EXISTS events_by_time ON events (start, end);
CREATE TABLE IF NOT EXISTS account_sync (
    account TEXT PRIMARY KEY,
    last_attempt TEXT,
    last_success TEXT,
    last_error TEXT
);
CREATE TABLE IF NOT EXISTS sent_alerts (
    key TEXT PRIMARY KEY,
    sent_at TEXT NOT NULL
);
"""

_COLUMNS = (
    "account, calendar_id, event_id, ical_uid, title, start, end, all_day, event_type, "
    "location, hangout_link, attendees, response_status, transparency, conference_link, updated"
)


def _ts(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime(_TS)


def _dt(value: str | None) -> datetime | None:
    return datetime.strptime(value, _TS).replace(tzinfo=UTC) if value else None


@dataclass(frozen=True, slots=True)
class SyncStatus:
    account: str
    last_attempt: datetime | None
    last_success: datetime | None
    last_error: str | None


class Store:
    def __init__(self, path: str | Path = DEFAULT_DB) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # WAL: sync escribe mientras watch lee sin bloquearse.
        self._conn = sqlite3.connect(self.path, timeout=10)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # --- eventos ---------------------------------------------------------------

    def replace_account_events(
        self, account: str, events: list[CalendarEvent], *, synced_at: datetime
    ) -> None:
        """Sustituye todos los eventos de la cuenta y marca la sincronización como correcta."""
        rows = [
            (
                e.account,
                e.calendar_id,
                e.event_id,
                e.ical_uid,
                e.title,
                _ts(e.start),
                _ts(e.end),
                int(e.all_day),
                e.event_type,
                e.location,
                e.hangout_link,
                json.dumps(list(e.attendees)),
                e.response_status,
                e.transparency,
                e.conference_link,
                e.updated,
            )
            for e in events
        ]
        with self._conn:
            self._conn.execute("DELETE FROM events WHERE account = ?", (account,))
            self._conn.executemany(
                f"INSERT OR REPLACE INTO events ({_COLUMNS}) VALUES ({', '.join('?' * 16)})",
                rows,
            )
            self._conn.execute(
                "INSERT INTO account_sync (account, last_attempt, last_success, last_error) "
                "VALUES (?, ?, ?, NULL) ON CONFLICT(account) DO UPDATE SET "
                "last_attempt = excluded.last_attempt, last_success = excluded.last_success, "
                "last_error = NULL",
                (account, _ts(synced_at), _ts(synced_at)),
            )

    def record_failure(self, account: str, error: str, *, attempted_at: datetime) -> None:
        """Registra un fallo sin tocar los eventos ni el último éxito de la cuenta."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO account_sync (account, last_attempt, last_success, last_error) "
                "VALUES (?, ?, NULL, ?) ON CONFLICT(account) DO UPDATE SET "
                "last_attempt = excluded.last_attempt, last_error = excluded.last_error",
                (account, _ts(attempted_at), error),
            )

    def retain_accounts(self, accounts: list[str]) -> None:
        """Olvida las cuentas que ya no están en la configuración."""
        marks = ", ".join("?" * len(accounts)) or "''"
        with self._conn:
            self._conn.execute(f"DELETE FROM events WHERE account NOT IN ({marks})", accounts)
            self._conn.execute(f"DELETE FROM account_sync WHERE account NOT IN ({marks})", accounts)

    def events_between(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        """Eventos que se solapan con [start, end), incluidos los que están en curso."""
        cur = self._conn.execute(
            f"SELECT {_COLUMNS} FROM events WHERE end > ? AND start < ? ORDER BY start, end, title",
            (_ts(start), _ts(end)),
        )
        return [
            CalendarEvent(
                account=r[0],
                calendar_id=r[1],
                event_id=r[2],
                ical_uid=r[3],
                title=r[4],
                start=_dt(r[5]),
                end=_dt(r[6]),
                all_day=bool(r[7]),
                event_type=r[8],
                location=r[9],
                hangout_link=r[10],
                attendees=tuple(json.loads(r[11])),
                response_status=r[12],
                transparency=r[13],
                conference_link=r[14],
                updated=r[15],
            )
            for r in cur.fetchall()
        ]

    def sync_status(self) -> list[SyncStatus]:
        cur = self._conn.execute(
            "SELECT account, last_attempt, last_success, last_error FROM account_sync "
            "ORDER BY account"
        )
        return [SyncStatus(r[0], _dt(r[1]), _dt(r[2]), r[3]) for r in cur.fetchall()]

    # --- alertas enviadas (calendar-watch) ---------------------------------------

    def was_sent(self, key: str) -> bool:
        cur = self._conn.execute("SELECT 1 FROM sent_alerts WHERE key = ?", (key,))
        return cur.fetchone() is not None

    def mark_sent(self, key: str, *, sent_at: datetime) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO sent_alerts (key, sent_at) VALUES (?, ?)",
                (key, _ts(sent_at)),
            )

    def prune_sent(self, *, before: datetime) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM sent_alerts WHERE sent_at < ?", (_ts(before),))
