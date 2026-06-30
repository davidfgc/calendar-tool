"""Lógica de negocio: parseo, filtrado de pendientes, combinación y orden.

Es código puro y determinista (recibe el ``now`` y la zona horaria), para poder
testearlo sin red ni reloj real.
"""

from __future__ import annotations

from datetime import datetime, timedelta, tzinfo

from .calendar_client import CalendarClient
from .models import CalendarEvent, CalendarRef

# eventType de Google para las entradas de "Ubicación de trabajo" (Home/Office).
# No son eventos a los que se asista; se excluyen por defecto.
WORKING_LOCATION = "workingLocation"


def day_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Inicio (00:00) y fin (24:00) del día de ``now``, en su misma zona horaria."""
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _parse_dt(value: dict, tz: tzinfo) -> tuple[datetime, bool]:
    """Convierte el campo start/end de Google en ``(datetime tz-aware, all_day)``."""
    if "dateTime" in value:
        dt = datetime.fromisoformat(value["dateTime"])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt.astimezone(tz), False
    # Evento de todo el día: campo 'date' (YYYY-MM-DD), sin hora.
    day = datetime.fromisoformat(value["date"]).replace(tzinfo=tz)
    return day, True


def parse_event(raw: dict, ref: CalendarRef, tz: tzinfo) -> CalendarEvent | None:
    """Mapea un recurso de evento de Google a CalendarEvent. None si no es utilizable."""
    if raw.get("status") == "cancelled":
        return None
    start_field = raw.get("start")
    end_field = raw.get("end")
    if not start_field or not end_field:
        return None

    start, all_day = _parse_dt(start_field, tz)
    end, _ = _parse_dt(end_field, tz)
    attendees = tuple(a["email"] for a in raw.get("attendees", []) if a.get("email"))
    return CalendarEvent(
        account=ref.account,
        calendar_id=ref.calendar_id,
        event_id=raw.get("id", ""),
        title=raw.get("summary", "(sin título)"),
        start=start,
        end=end,
        all_day=all_day,
        event_type=raw.get("eventType", "default"),
        location=raw.get("location", ""),
        hangout_link=raw.get("hangoutLink", ""),
        attendees=attendees,
    )


def is_pending(event: CalendarEvent, now: datetime) -> bool:
    """True si el evento aún no ha terminado (incluye los que están en curso)."""
    return event.end > now


def collect_pending_events(
    client: CalendarClient,
    refs: list[CalendarRef],
    day_start: datetime,
    day_end: datetime,
    now: datetime,
    tz: tzinfo,
    include_working_location: bool = False,
) -> list[CalendarEvent]:
    """Obtiene y filtra los eventos pendientes de hoy de los calendarios dados.

    Las entradas de "Ubicación de trabajo" (Home/Office) se excluyen salvo que
    ``include_working_location`` sea True.
    """
    collected: list[CalendarEvent] = []
    for ref in refs:
        raw_events = client.list_raw_events(
            ref.calendar_id, day_start.isoformat(), day_end.isoformat()
        )
        for raw in raw_events:
            event = parse_event(raw, ref, tz)
            if not event or not is_pending(event, now):
                continue
            if event.event_type == WORKING_LOCATION and not include_working_location:
                continue
            collected.append(event)
    return collected


def combine_and_sort(events: list[CalendarEvent]) -> list[CalendarEvent]:
    """Combina y ordena por hora de inicio; desempate estable por fin y luego título."""
    return sorted(events, key=lambda e: (e.start, e.end, e.title.casefold()))
