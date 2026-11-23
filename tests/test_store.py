"""Tests del almacén SQLite compartido por sync, watch y (en el futuro) pulse."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from calendar_tool.models import CalendarEvent
from calendar_tool.store import Store
from conftest import TZ

T0 = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)


def ev(event_id, hour, account="trabajo", **kw):
    return CalendarEvent(
        account=account,
        calendar_id="primary",
        event_id=event_id,
        title=f"Evento {event_id}",
        start=datetime(2026, 6, 29, hour, tzinfo=TZ),
        end=datetime(2026, 6, 29, hour + 1, tzinfo=TZ),
        **kw,
    )


def test_replace_y_consulta_conservan_los_campos(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    original = ev(
        "1",
        13,
        ical_uid="u1",
        response_status="accepted",
        transparency="transparent",
        conference_link="https://meet.google.com/x",
        attendees=("a@x.com",),
    )
    store.replace_account_events("trabajo", [original], synced_at=T0)
    got = store.events_between(datetime(2026, 6, 29, tzinfo=TZ), datetime(2026, 6, 30, tzinfo=TZ))
    assert got == [original]


def test_replace_borra_los_eventos_que_ya_no_existen(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.replace_account_events("trabajo", [ev("1", 9), ev("2", 10)], synced_at=T0)
    store.replace_account_events("trabajo", [ev("2", 10)], synced_at=T0)
    store.replace_account_events("cliente", [ev("3", 11, account="cliente")], synced_at=T0)
    got = store.events_between(datetime(2026, 6, 29, tzinfo=TZ), datetime(2026, 6, 30, tzinfo=TZ))
    assert [e.event_id for e in got] == ["2", "3"]


def test_events_between_incluye_los_que_estan_en_curso(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.replace_account_events("trabajo", [ev("1", 9), ev("2", 15)], synced_at=T0)
    got = store.events_between(datetime(2026, 6, 29, 9, 30, tzinfo=TZ), datetime(2026, 6, 29, 12, tzinfo=TZ))
    assert [e.event_id for e in got] == ["1"]


def test_fallo_conserva_eventos_y_ultimo_exito(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.replace_account_events("trabajo", [ev("1", 9)], synced_at=T0)
    store.record_failure("trabajo", "invalid_grant", attempted_at=T0 + timedelta(minutes=2))

    (status,) = store.sync_status()
    assert status.account == "trabajo"
    assert status.last_success == T0
    assert status.last_attempt == T0 + timedelta(minutes=2)
    assert status.last_error == "invalid_grant"
    assert len(store.events_between(T0 - timedelta(days=1), T0 + timedelta(days=1))) == 1


def test_exito_limpia_el_error(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.record_failure("trabajo", "red caída", attempted_at=T0)
    (status,) = store.sync_status()
    assert status.last_success is None
    store.replace_account_events("trabajo", [], synced_at=T0 + timedelta(minutes=2))
    (status,) = store.sync_status()
    assert status.last_error is None
    assert status.last_success == T0 + timedelta(minutes=2)


def test_retain_accounts_olvida_cuentas_quitadas_de_la_config(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.replace_account_events("vieja", [ev("1", 9, account="vieja")], synced_at=T0)
    store.replace_account_events("trabajo", [ev("2", 9)], synced_at=T0)
    store.retain_accounts(["trabajo"])
    assert [s.account for s in store.sync_status()] == ["trabajo"]
    got = store.events_between(T0 - timedelta(days=1), T0 + timedelta(days=1))
    assert [e.account for e in got] == ["trabajo"]


def test_alertas_enviadas(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    assert store.was_sent("k") is False
    store.mark_sent("k", sent_at=T0)
    assert store.was_sent("k") is True
    store.prune_sent(before=T0 + timedelta(seconds=1))
    assert store.was_sent("k") is False
