"""Dobles de prueba y constructores de datos, sin acceso a red."""

from __future__ import annotations

from calendar_tool.models import CalendarRef


class FakeCalendarClient:
    """Implementa la interfaz CalendarClient devolviendo datos en memoria."""

    def __init__(self, account: str, calendars=None, raw_events=None) -> None:
        self.account = account
        self._calendars: list[CalendarRef] = calendars or []
        # raw_events: dict[calendar_id] -> list[raw event dict]
        self._raw_events: dict[str, list[dict]] = raw_events or {}
        self.calls: list[tuple[str, str, str]] = []

    def list_calendars(self) -> list[CalendarRef]:
        return list(self._calendars)

    def list_raw_events(self, calendar_id: str, time_min: str, time_max: str) -> list[dict]:
        self.calls.append((calendar_id, time_min, time_max))
        return list(self._raw_events.get(calendar_id, []))


def raw_event(event_id: str, summary: str, start_iso: str, end_iso: str, **extra) -> dict:
    """Construye un recurso de evento con hora (como lo devuelve Google)."""
    event = {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
    }
    event.update(extra)
    return event


def all_day_event(event_id: str, summary: str, start_date: str, end_date: str, **extra) -> dict:
    """Construye un recurso de evento de todo el día."""
    event = {
        "id": event_id,
        "summary": summary,
        "start": {"date": start_date},
        "end": {"date": end_date},
    }
    event.update(extra)
    return event
