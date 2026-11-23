"""Tests de la consolidación: la misma reunión en varias cuentas cuenta una sola vez."""

from __future__ import annotations

from datetime import datetime

from calendar_tool.consolidate import dedupe
from calendar_tool.models import CalendarEvent
from conftest import TZ


def ev(account, event_id, *, uid="", hour=10, response="", title="Sync"):
    return CalendarEvent(
        account=account,
        calendar_id="primary",
        event_id=event_id,
        title=title,
        start=datetime(2026, 6, 29, hour, tzinfo=TZ),
        end=datetime(2026, 6, 29, hour + 1, tzinfo=TZ),
        ical_uid=uid,
        response_status=response,
    )


def test_misma_reunion_en_dos_cuentas_se_fusiona():
    meetings = dedupe([ev("trabajo", "a", uid="u1"), ev("cliente", "b", uid="u1")])
    assert len(meetings) == 1
    assert meetings[0].accounts == ("cliente", "trabajo")


def test_prefiere_la_copia_no_rechazada():
    meetings = dedupe(
        [
            ev("trabajo", "a", uid="u1", response="declined"),
            ev("cliente", "b", uid="u1", response="accepted"),
        ]
    )
    assert meetings[0].event.response_status == "accepted"
    assert meetings[0].event.account == "cliente"


def test_instancias_recurrentes_no_se_fusionan():
    # Las instancias de una serie comparten iCalUID pero no hora de inicio.
    meetings = dedupe(
        [ev("trabajo", "a_1", uid="serie", hour=9), ev("trabajo", "a_2", uid="serie", hour=11)]
    )
    assert [m.event.start.hour for m in meetings] == [9, 11]


def test_sin_ical_uid_no_se_fusiona():
    assert len(dedupe([ev("trabajo", "a"), ev("cliente", "a")])) == 2


def test_resultado_ordenado_por_inicio():
    meetings = dedupe([ev("x", "2", uid="b", hour=12), ev("x", "1", uid="a", hour=8)])
    assert [m.event.start.hour for m in meetings] == [8, 12]
