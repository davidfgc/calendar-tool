"""Tests de `calendar-tool sync` a través de la interfaz pública (cli.main)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from calendar_tool import cli, fetch
from calendar_tool.store import Store
from fakes import FakeCalendarClient, raw_event


def _config(tmp_path):
    path = tmp_path / "accounts.toml"
    path.write_text(
        '[accounts.personal]\ncredentials_file = "c.json"\ntoken_file = "t.json"\n'
        'calendars = ["primary"]\n'
        '[accounts.cliente]\ncredentials_file = "c.json"\ntoken_file = "t2.json"\n'
        'calendars = ["primary"]\n',
        encoding="utf-8",
    )
    return path


def _patch(monkeypatch, client, interactive_calls):
    def credentials(account, *, allow_interactive):
        interactive_calls.append(allow_interactive)
        if account.name == "cliente":
            raise RuntimeError("invalid_grant")
        return object()

    monkeypatch.setattr(fetch, "_default_credentials", credentials)
    monkeypatch.setattr(fetch, "_default_client", lambda creds, name: client)


def test_sync_guarda_eventos_y_registra_fallos(tmp_path, monkeypatch, capsys):
    now = datetime.now(UTC)
    start = (now + timedelta(hours=1)).isoformat()
    end = (now + timedelta(hours=2)).isoformat()
    client = FakeCalendarClient(
        "personal", raw_events={"primary": [raw_event("1", "Daily", start, end, iCalUID="u1")]}
    )
    interactive = []
    _patch(monkeypatch, client, interactive)
    db = tmp_path / "calendar.db"

    code = cli.main(["sync", "--config", str(_config(tmp_path)), "--db", str(db)])

    assert code == 1
    assert interactive == [False, False]  # nunca abre el navegador
    store = Store(db)
    events = store.events_between(now, now + timedelta(days=2))
    assert [(e.title, e.ical_uid) for e in events] == [("Daily", "u1")]
    status = {s.account: s for s in store.sync_status()}
    assert status["personal"].last_error is None
    assert status["cliente"].last_error == "invalid_grant"
    assert status["cliente"].last_success is None
    err = capsys.readouterr().err
    assert "Cuentas sincronizadas: 1 | con error: 1" in err
    assert "⚠ cliente: invalid_grant" in err
    assert "Eventos guardados: 1" in err
    # Ventana por defecto: desde ahora hasta 48 h después.
    time_min, time_max = (datetime.fromisoformat(v) for v in client.calls[0][1:])
    assert abs((time_min - now).total_seconds()) < 60
    assert time_max - time_min == timedelta(hours=48)


def test_sync_respeta_hours(tmp_path, monkeypatch):
    client = FakeCalendarClient("personal")
    _patch(monkeypatch, client, [])
    cli.main(
        ["sync", "--config", str(_config(tmp_path)), "--db", str(tmp_path / "d.db"), "--hours", "6"]
    )
    time_min, time_max = (datetime.fromisoformat(v) for v in client.calls[0][1:])
    assert time_max - time_min == timedelta(hours=6)


def test_sync_con_config_invalida_no_toca_la_base(tmp_path, capsys):
    db = tmp_path / "calendar.db"
    code = cli.main(["sync", "--config", str(tmp_path / "no-existe.toml"), "--db", str(db)])
    assert code == 2
    assert (
        "Error de configuración: No se encontró el archivo de configuración"
        in capsys.readouterr().err
    )
    assert not db.exists()


def test_help_menciona_el_subcomando_sync(capsys):
    try:
        cli.main(["--help"])
    except SystemExit:
        pass
    assert "calendar-tool sync" in capsys.readouterr().out
