"""Tests de los campos extra que necesita calendar-watch y de la extracción reutilizable."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from calendar_tool.events import fetch_window_events, parse_event
from calendar_tool.fetch import fetch_accounts
from calendar_tool.models import Account, CalendarRef
from fakes import FakeCalendarClient, raw_event

REF = CalendarRef("trabajo", "primary")
START = "2026-06-29T13:00:00-07:00"
END = "2026-06-29T14:00:00-07:00"


def _parse(tz, **extra):
    return parse_event(raw_event("1", "Reunión", START, END, **extra), REF, tz)


def test_parse_extrae_ical_uid_y_updated(tz):
    ev = _parse(tz, iCalUID="abc@google.com", updated="2026-06-28T10:00:00.000Z")
    assert ev.ical_uid == "abc@google.com"
    assert ev.updated == "2026-06-28T10:00:00.000Z"


def test_parse_respuesta_del_propio_asistente(tz):
    ev = _parse(
        tz,
        attendees=[
            {"email": "otro@x.com", "responseStatus": "accepted"},
            {"email": "yo@x.com", "self": True, "responseStatus": "declined"},
        ],
    )
    assert ev.response_status == "declined"


def test_parse_sin_asistentes_no_tiene_respuesta(tz):
    assert _parse(tz).response_status == ""


@pytest.mark.parametrize(
    ("raw", "expected"), [({}, "opaque"), ({"transparency": "transparent"}, "transparent")]
)
def test_parse_transparencia(tz, raw, expected):
    assert _parse(tz, **raw).transparency == expected


def test_enlace_prefiere_hangout_link(tz):
    ev = _parse(tz, hangoutLink="https://meet.google.com/aaa", location="https://zoom.us/j/1")
    assert ev.conference_link == "https://meet.google.com/aaa"


def test_enlace_desde_conference_data(tz):
    ev = _parse(
        tz,
        conferenceData={
            "entryPoints": [
                {"entryPointType": "phone", "uri": "tel:+1-555"},
                {"entryPointType": "video", "uri": "https://acme.zoom.us/j/123"},
            ]
        },
    )
    assert ev.conference_link == "https://acme.zoom.us/j/123"


def test_enlace_zoom_en_ubicacion(tz):
    ev = _parse(tz, location="Sala 3 / https://acme.zoom.us/j/999?pwd=x")
    assert ev.conference_link == "https://acme.zoom.us/j/999?pwd=x"


def test_enlace_teams_en_descripcion(tz):
    ev = _parse(
        tz,
        description='Únete: <a href="https://teams.microsoft.com/l/meetup-join/19%3a">aquí</a>',
    )
    assert ev.conference_link == "https://teams.microsoft.com/l/meetup-join/19%3a"


def test_sin_enlace(tz):
    ev = _parse(tz, location="Oficina", description="Traer laptop")
    assert ev.conference_link == ""


def test_fetch_window_events_no_filtra_por_pendiente_y_usa_la_ventana(now, tz):
    client = FakeCalendarClient(
        "trabajo",
        raw_events={
            "primary": [
                raw_event("p", "Pasado", "2026-06-29T08:00:00-07:00", "2026-06-29T09:00:00-07:00"),
                raw_event("m", "Mañana", "2026-06-30T09:00:00-07:00", "2026-06-30T10:00:00-07:00"),
            ]
        },
    )
    time_min, time_max = now, now + timedelta(hours=48)
    events = fetch_window_events(client, [REF], time_min, time_max, tz)
    assert [e.title for e in events] == ["Pasado", "Mañana"]
    assert client.calls == [("primary", time_min.isoformat(), time_max.isoformat())]


def test_fetch_accounts_aisla_fallos_por_cuenta(now, tz):
    ok = Account(name="personal", credentials_file="c.json", calendars=["primary"])
    bad = Account(name="cliente", credentials_file="c.json")
    clients = {
        "personal": FakeCalendarClient(
            "personal",
            raw_events={"primary": [raw_event("1", "Daily", START, END)]},
        )
    }

    def credentials_fn(account, *, allow_interactive):
        assert allow_interactive is False
        if account.name == "cliente":
            raise RuntimeError("token revocado")
        return object()

    results = fetch_accounts(
        [ok, bad],
        time_min=datetime(2026, 6, 29, tzinfo=tz),
        time_max=datetime(2026, 6, 30, tzinfo=tz),
        tz=tz,
        allow_interactive=False,
        credentials_fn=credentials_fn,
        client_fn=lambda creds, name: clients[name],
    )
    by_name = {r.account: r for r in results}
    assert [e.title for e in by_name["personal"].events] == ["Daily"]
    assert by_name["personal"].error is None
    assert by_name["cliente"].events == []
    assert by_name["cliente"].error == "token revocado"
