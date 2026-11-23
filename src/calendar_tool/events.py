"""Lógica de negocio: parseo, filtrado de pendientes, combinación y orden.

Es código puro y determinista (recibe el ``now`` y la zona horaria), para poder
testearlo sin red ni reloj real.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, tzinfo

from .calendar_client import CalendarClient
from .models import CalendarEvent, CalendarRef

# eventType de Google para las entradas de "Ubicación de trabajo" (Home/Office).
# No son eventos a los que se asista; se excluyen por defecto.
WORKING_LOCATION = "workingLocation"

# Enlaces de videollamada reconocidos en ubicación/descripción.
_MEETING_URL = re.compile(
    r"https://(?:[\w-]+\.)?(?:zoom\.us|teams\.microsoft\.com|teams\.live\.com|meet\.google\.com"
    r"|webex\.com)/[^\s\"'<>]+"
)


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
    own = next((a for a in raw.get("attendees", []) if a.get("self")), {})
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
        ical_uid=raw.get("iCalUID", ""),
        response_status=own.get("responseStatus", ""),
        transparency=raw.get("transparency", "opaque"),
        conference_link=conference_link(raw),
        updated=raw.get("updated", ""),
    )


def conference_link(raw: dict) -> str:
    """Mejor enlace para unirse: hangoutLink, conferenceData (video) o URL en el texto."""
    if raw.get("hangoutLink"):
        return raw["hangoutLink"]
    for entry in raw.get("conferenceData", {}).get("entryPoints", []):
        if entry.get("entryPointType") == "video" and entry.get("uri"):
            return entry["uri"]
    for text in (raw.get("location", ""), raw.get("description", "")):
        match = _MEETING_URL.search(text or "")
        if match:
            return match.group(0)
    return ""


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
    events = collect_events(client, refs, day_start, day_end, tz, include_working_location)
    return [e for e in events if is_pending(e, now)]


def collect_events(
    client: CalendarClient,
    refs: list[CalendarRef],
    time_min: datetime,
    time_max: datetime,
    tz: tzinfo,
    include_working_location: bool = False,
) -> list[CalendarEvent]:
    """Obtiene los eventos de los calendarios dados en la ventana [time_min, time_max).

    Google devuelve los eventos cuyo fin es posterior a ``time_min``, de modo que los
    eventos en curso se incluyen.
    """
    collected: list[CalendarEvent] = []
    for ref in refs:
        raw_events = client.list_raw_events(
            ref.calendar_id, time_min.isoformat(), time_max.isoformat()
        )
        for raw in raw_events:
            event = parse_event(raw, ref, tz)
            if not event:
                continue
            if event.event_type == WORKING_LOCATION and not include_working_location:
                continue
            collected.append(event)
    return collected


def combine_and_sort(events: list[CalendarEvent]) -> list[CalendarEvent]:
    """Combina y ordena por hora de inicio; desempate estable por fin y luego título."""
    return sorted(events, key=lambda e: (e.start, e.end, e.title.casefold()))
