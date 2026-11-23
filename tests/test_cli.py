"""Tests del CLI `calendar-tool` (sin subcomando) a través de su interfaz pública."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from calendar_tool import cli, fetch
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


def test_calendar_tool_sigue_volcando_solo_pendientes_de_hoy(tmp_path, monkeypatch, capsys):
    now = datetime.now().astimezone()
    fmt = "%Y-%m-%dT%H:%M:%S%z"
    past = raw_event(
        "p",
        "Pasado",
        (now - timedelta(hours=2)).strftime(fmt),
        (now - timedelta(hours=1)).strftime(fmt),
    )
    upcoming = raw_event(
        "f",
        "Futuro",
        (now + timedelta(minutes=1)).strftime(fmt),
        (now + timedelta(minutes=2)).strftime(fmt),
    )
    client = FakeCalendarClient("personal", raw_events={"primary": [past, upcoming]})

    def credentials(account, *, allow_interactive):
        assert allow_interactive is False
        if account.name == "cliente":
            raise RuntimeError("token revocado")
        return object()

    monkeypatch.setattr(fetch, "_default_credentials", credentials)
    monkeypatch.setattr(fetch, "_default_client", lambda creds, name: client)
    out = tmp_path / "out.json"

    code = cli.main(["--config", str(_config(tmp_path)), "--no-interactive", "-o", str(out)])

    assert code == 1  # una cuenta falló
    assert [e["title"] for e in json.loads(out.read_text(encoding="utf-8"))] == ["Futuro"]
    err = capsys.readouterr().err
    assert "Cuentas leídas: 1 | con error: 1" in err
    assert "⚠ cliente: token revocado" in err
    # La ventana consultada sigue siendo el día actual.
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    assert client.calls[0][1] == day_start.isoformat()


def test_ayuda_ajusta_la_descripcion_y_conserva_el_epilogo(monkeypatch):
    monkeypatch.setenv("COLUMNS", "80")
    help_text = cli.build_parser().format_help()
    assert max(len(line) for line in help_text.splitlines()) <= 80
    assert "--range month." in help_text
    assert "  calendar-tool sync   guarda en SQLite" in help_text
