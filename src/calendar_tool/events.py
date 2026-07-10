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


def month_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Inicio (día 1, 00:00) y fin exclusivo (día 1 del mes siguiente, 00:00) del mes.

    El límite superior exclusivo en el primer instante del mes siguiente equivale a
    "hasta el último día del mes a las 23:59:59" y es el ``timeMax`` que espera la API.
    Calcular el mes siguiente con ``day=1`` evita construir fechas inválidas, así que
    las longitudes de mes (28/29/30/31) y el salto diciembre→enero salen sin casos
    especiales.
    """
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


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


def collect_events(
    client: CalendarClient,
    refs: list[CalendarRef],
    time_min: datetime,
    time_max: datetime,
    now: datetime,
    tz: tzinfo,
    pending_only: bool = True,
    include_working_location: bool = False,
) -> list[CalendarEvent]:
    """Obtiene y filtra los eventos de los calendarios dados en ``[time_min, time_max)``.

    - ``pending_only=True`` (modo día): solo deja los eventos cuya hora de fin es
      posterior a ``now`` (incluye los que están en curso). ``pending_only=False``
      (modo mes): incluye también los eventos ya terminados dentro de la ventana.
    - Los eventos de todo el día se excluyen en ambos modos.
    - Las entradas de "Ubicación de trabajo" (Home/Office) se excluyen salvo que
      ``include_working_location`` sea True; solo entonces se incluyen, aun siendo
      eventos de todo el día.
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
            # La Ubicación de trabajo (all-day) tiene su propio flag y se evalúa antes
            # que la exclusión general de all-day para no romper ese comportamiento.
            if event.event_type == WORKING_LOCATION:
                if not include_working_location:
                    continue
            elif event.all_day:
                continue
            if pending_only and not is_pending(event, now):
                continue
            collected.append(event)
    return collected


def combine_and_sort(events: list[CalendarEvent]) -> list[CalendarEvent]:
    """Combina y ordena por hora de inicio; desempate estable por fin y luego título."""
    return sorted(events, key=lambda e: (e.start, e.end, e.title.casefold()))
