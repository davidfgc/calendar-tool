"""Consolidación: la misma reunión presente en varias cuentas cuenta una sola vez."""

from __future__ import annotations

from dataclasses import dataclass

from .models import CalendarEvent

# Preferencia al elegir la copia representativa (menor = mejor).
_RESPONSE_RANK = {"accepted": 0, "": 0, "tentative": 1, "needsAction": 2, "declined": 3}


@dataclass(frozen=True, slots=True)
class Meeting:
    """Una reunión única, con la copia representativa y las cuentas donde aparece."""

    event: CalendarEvent
    accounts: tuple[str, ...]


def _key(event: CalendarEvent) -> tuple:
    # Las instancias de una serie recurrente comparten iCalUID: se distinguen por inicio.
    if event.ical_uid:
        return ("uid", event.ical_uid, event.start.timestamp())
    return ("id", event.account, event.calendar_id, event.event_id)


def dedupe(events: list[CalendarEvent]) -> list[Meeting]:
    """Fusiona las copias de la misma reunión y ordena por inicio."""
    groups: dict[tuple, list[CalendarEvent]] = {}
    for event in events:
        groups.setdefault(_key(event), []).append(event)

    meetings = []
    for copies in groups.values():
        best = min(copies, key=lambda e: _RESPONSE_RANK.get(e.response_status, 2))
        meetings.append(Meeting(best, tuple(sorted({e.account for e in copies}))))
    return sorted(meetings, key=lambda m: (m.event.start, m.event.end, m.event.title.casefold()))
