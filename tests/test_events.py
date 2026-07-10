"""Tests de la lógica de eventos: parseo, filtro de pendientes, combinación y orden."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from calendar_tool.events import (
    collect_events,
    combine_and_sort,
    day_bounds,
    is_pending,
    month_bounds,
    parse_event,
)
from calendar_tool.models import CalendarEvent, CalendarRef
from fakes import FakeCalendarClient, all_day_event, raw_event

REF = CalendarRef("personal", "primary")


def test_day_bounds_cubre_el_dia_completo(now):
    start, end = day_bounds(now)
    assert (start.hour, start.minute, start.second) == (0, 0, 0)
    assert end - start == timedelta(days=1)
    assert start <= now < end


def test_parse_evento_con_hora(tz):
    ev = parse_event(
        raw_event("1", "Reunión", "2026-06-29T13:00:00-07:00", "2026-06-29T14:00:00-07:00"),
        REF,
        tz,
    )
    assert ev is not None
    assert ev.title == "Reunión"
    assert ev.all_day is False
    assert ev.start.hour == 13
    assert ev.account == "personal"
    assert ev.calendar_id == "primary"


def test_parse_evento_todo_el_dia(tz):
    ev = parse_event(all_day_event("2", "Festivo", "2026-06-29", "2026-06-30"), REF, tz)
    assert ev is not None
    assert ev.all_day is True
    assert ev.start.hour == 0


def test_parse_cancelado_devuelve_none(tz):
    assert parse_event({"status": "cancelled", "id": "x"}, REF, tz) is None


def test_parse_extrae_asistentes_y_enlace(tz):
    ev = parse_event(
        raw_event(
            "3",
            "Daily",
            "2026-06-29T13:00:00-07:00",
            "2026-06-29T13:15:00-07:00",
            hangoutLink="https://meet.google.com/abc",
            attendees=[{"email": "a@x.com"}, {"email": "b@x.com"}, {"optional": True}],
        ),
        REF,
        tz,
    )
    assert ev.attendees == ("a@x.com", "b@x.com")
    assert ev.hangout_link == "https://meet.google.com/abc"


def test_is_pending_excluye_terminados(now, tz):
    pasado = parse_event(
        raw_event("p", "Pasado", "2026-06-29T09:00:00-07:00", "2026-06-29T10:00:00-07:00"),
        REF,
        tz,
    )
    assert is_pending(pasado, now) is False


def test_is_pending_incluye_en_curso(now, tz):
    en_curso = parse_event(
        raw_event("o", "En curso", "2026-06-29T11:30:00-07:00", "2026-06-29T12:30:00-07:00"),
        REF,
        tz,
    )
    assert is_pending(en_curso, now) is True


def test_collect_pending_filtra_y_mapea(now, tz):
    client = FakeCalendarClient(
        "trabajo",
        raw_events={
            "primary": [
                raw_event("p", "Pasado", "2026-06-29T08:00:00-07:00", "2026-06-29T09:00:00-07:00"),
                raw_event("f", "Futuro", "2026-06-29T15:00:00-07:00", "2026-06-29T16:00:00-07:00"),
            ]
        },
    )
    ref = CalendarRef("trabajo", "primary")
    start, end = day_bounds(now)
    events = collect_events(client, [ref], start, end, now, tz)
    assert [e.title for e in events] == ["Futuro"]
    # Se consultó con la ventana del día.
    assert client.calls == [("primary", start.isoformat(), end.isoformat())]


def test_working_location_excluida_por_defecto(now, tz):
    raw = all_day_event("wl", "Home", "2026-06-29", "2026-06-30", eventType="workingLocation")
    client = FakeCalendarClient("personal", raw_events={"primary": [raw]})
    ref = CalendarRef("personal", "primary")
    start, end = day_bounds(now)

    # Por defecto, las entradas de Ubicación de trabajo no aparecen.
    assert collect_events(client, [ref], start, end, now, tz) == []

    # Con el flag explícito, sí se incluyen y conservan su event_type (aun siendo all-day).
    incluidos = collect_events(client, [ref], start, end, now, tz, include_working_location=True)
    assert [e.title for e in incluidos] == ["Home"]
    assert incluidos[0].event_type == "workingLocation"


def test_parse_event_type_por_defecto(tz):
    ev = parse_event(
        raw_event("1", "Reunión", "2026-06-29T13:00:00-07:00", "2026-06-29T14:00:00-07:00"),
        REF,
        tz,
    )
    assert ev.event_type == "default"


def test_combine_and_sort_ordena_y_desempata():
    tz = ZoneInfo("America/Los_Angeles")

    def ev(title, start_h, end_h):
        return CalendarEvent(
            account="a",
            calendar_id="primary",
            event_id=title,
            title=title,
            start=datetime(2026, 6, 29, start_h, tzinfo=tz),
            end=datetime(2026, 6, 29, end_h, tzinfo=tz),
        )

    ordenado = combine_and_sort([ev("Beta", 10, 11), ev("Alfa", 10, 11), ev("Cero", 9, 10)])
    # Cero empieza antes; Alfa/Beta empatan en inicio y fin -> desempate por título.
    assert [e.title for e in ordenado] == ["Cero", "Alfa", "Beta"]


def test_month_bounds_cubre_el_mes_completo(now):
    # now = 2026-06-29 -> junio.
    start, end = month_bounds(now)
    assert (start.year, start.month, start.day) == (2026, 6, 1)
    assert (start.hour, start.minute, start.second, start.microsecond) == (0, 0, 0, 0)
    # Fin exclusivo: primer instante del mes siguiente (julio).
    assert (end.year, end.month, end.day) == (2026, 7, 1)
    assert (end.hour, end.minute, end.second) == (0, 0, 0)
    assert start <= now < end


def test_month_bounds_salto_de_anio_en_diciembre(tz):
    start, end = month_bounds(datetime(2026, 12, 15, 9, 0, tzinfo=tz))
    assert (start.year, start.month, start.day) == (2026, 12, 1)
    assert (end.year, end.month, end.day) == (2027, 1, 1)


def test_month_bounds_longitudes_de_mes(tz):
    # Febrero no bisiesto (2026) -> el fin cae el 1 de marzo.
    _, fin_feb = month_bounds(datetime(2026, 2, 10, tzinfo=tz))
    assert (fin_feb.year, fin_feb.month, fin_feb.day) == (2026, 3, 1)
    # Febrero bisiesto (2028) -> también el 1 de marzo, sin construir el 29/30.
    start_bis, fin_bis = month_bounds(datetime(2028, 2, 10, tzinfo=tz))
    assert (start_bis.month, start_bis.day) == (2, 1)
    assert (fin_bis.month, fin_bis.day) == (3, 1)
    # Mes de 31 días (enero) -> el fin cae el 1 de febrero.
    _, fin_ene = month_bounds(datetime(2026, 1, 5, tzinfo=tz))
    assert (fin_ene.year, fin_ene.month, fin_ene.day) == (2026, 2, 1)


def test_collect_events_modo_mes_incluye_terminados(now, tz):
    # En modo mes (pending_only=False) se ven también los eventos que ya terminaron.
    client = FakeCalendarClient(
        "personal",
        raw_events={
            "primary": [
                raw_event("a", "Pasado", "2026-06-10T08:00:00-07:00", "2026-06-10T09:00:00-07:00"),
                raw_event("b", "Futuro", "2026-06-29T15:00:00-07:00", "2026-06-29T16:00:00-07:00"),
            ]
        },
    )
    ref = CalendarRef("personal", "primary")
    start, end = month_bounds(now)
    events = collect_events(client, [ref], start, end, now, tz, pending_only=False)
    assert sorted(e.title for e in events) == ["Futuro", "Pasado"]
    # Se consultó con la ventana del mes.
    assert client.calls == [("primary", start.isoformat(), end.isoformat())]


def test_collect_events_modo_mes_conserva_evento_a_caballo(now, tz):
    # El solapamiento con la ventana lo resuelve la API; aquí verificamos que nuestro
    # filtrado no descarta un evento con hora que cruza el borde del mes.
    client = FakeCalendarClient(
        "personal",
        raw_events={
            "primary": [
                raw_event(
                    "x", "A caballo", "2026-05-31T22:00:00-07:00", "2026-06-01T01:00:00-07:00"
                ),
            ]
        },
    )
    ref = CalendarRef("personal", "primary")
    start, end = month_bounds(now)
    events = collect_events(client, [ref], start, end, now, tz, pending_only=False)
    assert [e.title for e in events] == ["A caballo"]


def test_collect_events_excluye_all_day_en_ambos_modos(now, tz):
    festivo = all_day_event("h", "Festivo", "2026-06-29", "2026-06-30")
    client = FakeCalendarClient("personal", raw_events={"primary": [festivo]})
    ref = CalendarRef("personal", "primary")
    day_start, day_end = day_bounds(now)
    month_start, month_end = month_bounds(now)

    en_dia = collect_events(client, [ref], day_start, day_end, now, tz)
    en_mes = collect_events(client, [ref], month_start, month_end, now, tz, pending_only=False)
    assert en_dia == []
    assert en_mes == []
