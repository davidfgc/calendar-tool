"""Tests del planificador de avisos (puro): recordatorios, conflictos y cuentas sin actualizar."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from calendar_tool.alerts import plan_alerts
from calendar_tool.consolidate import Meeting
from calendar_tool.models import CalendarEvent
from calendar_tool.store import SyncStatus
from conftest import TZ

START = datetime(2026, 6, 29, 13, 0, tzinfo=TZ)
# Sincronizada "recientemente" para todos los relojes de los tests de recordatorios/conflictos.
FRESH = [SyncStatus("trabajo", START, START + timedelta(hours=1), None)]


def meeting(title="Daily", start=START, minutes=60, uid=None, accounts=("trabajo",), **kw):
    event = CalendarEvent(
        account=accounts[0],
        calendar_id="primary",
        event_id=title,
        title=title,
        start=start,
        end=start + timedelta(minutes=minutes),
        ical_uid=uid or f"{title}@x",
        **kw,
    )
    return Meeting(event, accounts)


def plan(meetings, now, sent=(), statuses=None):
    sent = set(sent)
    return plan_alerts(
        meetings,
        FRESH if statuses is None else statuses,
        now,
        reminders=(10, 1),
        stale_after=timedelta(minutes=15),
        is_sent=sent.__contains__,
        tz=TZ,
    )


def keys(alerts):
    return {k for a in alerts for k in a.marks}


# --- recordatorios -------------------------------------------------------------


def test_recordatorio_a_10_min_con_enlace():
    m = meeting(conference_link="https://meet.google.com/x", accounts=("cliente", "trabajo"))
    (alert,) = plan([m], START - timedelta(minutes=10))
    assert alert.kind == "reminder"
    assert alert.title == "Reunión en 10 min"
    assert alert.message == "Daily · 13:00 · cliente, trabajo"
    assert alert.link == "https://meet.google.com/x"
    assert alert.priority == 4


def test_recordatorio_a_1_min_es_urgente():
    m = meeting()
    sent = keys(plan([m], START - timedelta(minutes=10)))
    (alert,) = plan([m], START - timedelta(minutes=1), sent)
    assert alert.title == "Reunión en 1 min"
    assert alert.priority == 5


def test_no_repite_un_recordatorio_enviado():
    m = meeting()
    sent = keys(plan([m], START - timedelta(minutes=10)))
    assert plan([m], START - timedelta(minutes=9), sent) == []


def test_reunion_agendada_a_ultima_hora_avisa_una_sola_vez():
    m = meeting()
    (alert,) = plan([m], START - timedelta(seconds=30))
    assert alert.title == "Reunión en 1 min"
    assert len(alert.marks) == 2  # el aviso de 10 min ya no tiene sentido


def test_reunion_a_6_min_dice_los_minutos_reales():
    (alert,) = plan([meeting()], START - timedelta(minutes=6))
    assert alert.title == "Reunión en 6 min"


def test_sin_recordatorio_para_rechazadas_todo_el_dia_o_fuera_de_oficina():
    now = START - timedelta(minutes=1)
    assert plan([meeting(response_status="declined")], now) == []
    assert plan([meeting(all_day=True)], now) == []
    assert plan([meeting(event_type="outOfOffice")], now) == []


def test_sin_recordatorio_si_ya_empezo():
    assert plan([meeting()], START + timedelta(seconds=1)) == []


def test_reunion_movida_vuelve_a_avisar():
    original = meeting()
    sent = keys(plan([original], START - timedelta(minutes=10)))
    moved = meeting(start=START + timedelta(minutes=30))
    (alert,) = plan([moved], START + timedelta(minutes=20), sent)
    assert alert.title == "Reunión en 10 min"


# --- conflictos -----------------------------------------------------------------

NOW = START - timedelta(hours=2)


def test_conflicto_entre_reuniones_que_se_solapan():
    a = meeting("Daily", minutes=60, accounts=("trabajo",))
    b = meeting("Cliente", start=START + timedelta(minutes=30), accounts=("cliente",))
    (alert,) = plan([a, b], NOW)
    assert alert.kind == "conflict"
    assert alert.title == "Conflicto de reuniones"
    assert alert.message == (
        "Daily (13:00–14:00, trabajo) se solapa con Cliente (13:30–14:30, cliente)"
    )
    # Misma clave sin importar el orden; no se repite.
    assert plan([b, a], NOW, keys([alert])) == []


def test_conflicto_en_otro_dia_muestra_la_fecha():
    a = meeting("A", start=START + timedelta(days=1))
    b = meeting("B", start=START + timedelta(days=1, minutes=15))
    (alert,) = plan([a, b], NOW)
    assert alert.message.startswith("A (30/06 13:00–14:00, trabajo)")


def test_no_son_conflicto():
    a = meeting("A")
    seguida = meeting("B", start=START + timedelta(minutes=60))
    disponible = meeting("C", start=START + timedelta(minutes=10), transparency="transparent")
    rechazada = meeting("D", start=START + timedelta(minutes=10), response_status="declined")
    todo_el_dia = meeting("E", start=START, minutes=24 * 60, all_day=True)
    assert plan([a, seguida, disponible, rechazada, todo_el_dia], NOW) == []


# --- cuentas sin actualizar -------------------------------------------------------


def test_cuenta_sin_actualizar_mas_de_15_min():
    now = START + timedelta(minutes=16)
    status = SyncStatus("work", now, START, "La cuenta 'work' requiere reautenticación")
    (alert,) = plan([], now, statuses=[status])
    assert alert.kind == "stale"
    assert alert.title == "Calendario sin actualizar"
    assert alert.message == (
        "La cuenta 'work' no se actualiza desde las 13:00 "
        "(La cuenta 'work' requiere reautenticación). "
        "Vuelve a iniciar sesión: uv run calendar-tool --account work"
    )
    assert plan([], now + timedelta(minutes=5), keys([alert]), [status]) == []


def test_cuenta_actualizada_hace_14_min_no_avisa():
    status = SyncStatus("work", START, START, None)
    assert plan([], START + timedelta(minutes=14), statuses=[status]) == []


def test_cuenta_que_nunca_sincronizo():
    status = SyncStatus("baires", START, None, "requiere consentimiento interactivo")
    (alert,) = plan([], START, statuses=[status])
    assert alert.message.startswith("La cuenta 'baires' nunca se ha sincronizado")


def test_sin_datos_de_sincronizacion():
    (alert,) = plan([], START, statuses=[])
    assert alert.kind == "stale"
    assert alert.message == "No hay datos de sincronización: ¿está corriendo calendar-tool sync?"


def test_vuelve_a_avisar_en_un_nuevo_episodio():
    first = SyncStatus("work", None, START, "x")
    sent = keys(plan([], START + timedelta(minutes=20), statuses=[first]))
    later = SyncStatus("work", None, START + timedelta(hours=1), "x")
    assert len(plan([], START + timedelta(hours=2), sent, [later])) == 1


def test_utc_y_zona_local():
    # Los eventos vienen de SQLite en UTC; se muestran en la zona local.
    m = meeting(start=START.astimezone(UTC))
    (alert,) = plan([m], START - timedelta(minutes=10))
    assert "13:00" in alert.message
