"""Extracción multi-cuenta reutilizable (la usan `calendar-tool` y `calendar-tool sync`).

Resuelve credenciales y calendarios de cada cuenta y aísla los fallos: si una cuenta
falla, las demás se entregan igualmente y el error queda en su ``AccountResult``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, tzinfo

from .events import fetch_window_events
from .models import Account, CalendarEvent, CalendarRef


@dataclass
class AccountResult:
    account: str
    events: list[CalendarEvent] = field(default_factory=list)
    error: str | None = None


def _default_credentials(account: Account, *, allow_interactive: bool):
    from .auth import credentials_for_account

    return credentials_for_account(account, allow_interactive=allow_interactive)


def _default_client(credentials, account_name: str):
    from .calendar_client import GoogleCalendarClient

    return GoogleCalendarClient.from_credentials(credentials, account_name)


def refs_for_account(client, account: Account, calendars_override=None) -> list[CalendarRef]:
    wanted = calendars_override or account.calendars
    if wanted:
        return [CalendarRef(account=account.name, calendar_id=c) for c in wanted]
    # Sin lista explícita: leer todos los calendarios de la cuenta.
    return client.list_calendars()


def fetch_accounts(
    accounts: list[Account],
    *,
    time_min: datetime,
    time_max: datetime,
    tz: tzinfo,
    allow_interactive: bool,
    calendars_override: list[str] | None = None,
    include_working_location: bool = False,
    credentials_fn: Callable | None = None,
    client_fn: Callable | None = None,
) -> list[AccountResult]:
    """Lee los eventos de ``[time_min, time_max)`` de cada cuenta, aislando sus fallos."""
    credentials_fn = credentials_fn or _default_credentials
    client_fn = client_fn or _default_client
    results: list[AccountResult] = []
    for account in accounts:
        try:
            creds = credentials_fn(account, allow_interactive=allow_interactive)
            client = client_fn(creds, account.name)
            refs = refs_for_account(client, account, calendars_override)
            events = fetch_window_events(
                client, refs, time_min, time_max, tz, include_working_location
            )
            results.append(AccountResult(account.name, events))
        except Exception as exc:  # aísla el fallo de esta cuenta
            results.append(AccountResult(account.name, error=str(exc)))
    return results
