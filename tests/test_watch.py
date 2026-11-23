"""Tests de calendar-watch: ciclo, notificador macOS, config [watch] y plists de launchd."""

from __future__ import annotations

import plistlib
from datetime import UTC, datetime, timedelta

import pytest

from calendar_tool import watch
from calendar_tool.alerts import Alert
from calendar_tool.config import ConfigError, WatchConfig, load_config
from calendar_tool.models import CalendarEvent
from calendar_tool.store import Store
from conftest import TZ

NOW = datetime(2026, 6, 29, 12, 50, tzinfo=TZ)


class FakeNotifier:
    def __init__(self, fail=False):
        self.sent: list[Alert] = []
        self.fail = fail

    def send(self, alert):
        if self.fail:
            raise RuntimeError("sin red")
        self.sent.append(alert)


def _event(account, event_id, start, uid="u1"):
    return CalendarEvent(
        account=account,
        calendar_id="primary",
        event_id=event_id,
        title="Kickoff",
        start=start,
        end=start + timedelta(hours=1),
        ical_uid=uid,
    )


def _store(tmp_path, events_by_account):
    store = Store(tmp_path / "c.db")
    for account, events in events_by_account.items():
        store.replace_account_events(account, events, synced_at=NOW)
    return store


def test_ciclo_misma_reunion_en_dos_cuentas_avisa_una_vez_y_no_es_conflicto(tmp_path):
    start = NOW + timedelta(minutes=10)
    store = _store(
        tmp_path,
        {"trabajo": [_event("trabajo", "a", start)], "cliente": [_event("cliente", "b", start)]},
    )
    notifier = FakeNotifier()
    logs = []

    alerts = watch.run_cycle(store, WatchConfig(), [notifier], NOW, TZ, log=logs.append)

    assert [a.title for a in alerts] == ["Reunión en 10 min"]
    assert notifier.sent[0].message == "Kickoff · 13:00 · cliente, trabajo"
    assert logs == [
        "2026-06-29 12:50:00 [reminder] Reunión en 10 min — Kickoff · 13:00 · cliente, trabajo"
    ]
    # El siguiente ciclo no repite.
    assert (
        watch.run_cycle(
            store, WatchConfig(), [notifier], NOW + timedelta(seconds=15), TZ, log=logs.append
        )
        == []
    )
    assert len(notifier.sent) == 1


def test_un_notificador_que_falla_no_bloquea_a_los_demas(tmp_path):
    store = _store(tmp_path, {"trabajo": [_event("trabajo", "a", NOW + timedelta(minutes=1))]})
    roto, bueno = FakeNotifier(fail=True), FakeNotifier()
    logs = []
    watch.run_cycle(store, WatchConfig(), [roto, bueno], NOW, TZ, log=logs.append)
    assert [a.title for a in bueno.sent] == ["Reunión en 1 min"]
    assert "⚠ FakeNotifier: sin red" in logs
    assert watch.run_cycle(store, WatchConfig(), [bueno], NOW, TZ, log=logs.append) == []


def test_ciclo_respeta_los_recordatorios_configurados(tmp_path):
    store = _store(tmp_path, {"trabajo": [_event("trabajo", "a", NOW + timedelta(minutes=10))]})
    cfg = WatchConfig(reminders=(5,))
    assert watch.run_cycle(store, cfg, [FakeNotifier()], NOW, TZ, log=lambda _: None) == []


# --- notificador macOS ---------------------------------------------------------


def _alert(**kw):
    base = dict(kind="reminder", title='Reunión "X"', message="Daily · 13:00", marks=("k",))
    base.update(kw)
    return Alert(**base)


def test_mac_usa_terminal_notifier_con_enlace():
    calls = []
    notifier = watch.MacNotifier(run=lambda cmd, **kw: calls.append(cmd), which=lambda _: "/bin/tn")
    notifier.send(_alert(link="https://meet.google.com/x"))
    assert calls == [
        [
            "/bin/tn",
            "-title",
            'Reunión "X"',
            "-message",
            "Daily · 13:00",
            "-sound",
            "Glass",
            "-open",
            "https://meet.google.com/x",
        ]
    ]


def test_mac_sin_terminal_notifier_usa_osascript_sin_interpolar_texto():
    calls = []
    notifier = watch.MacNotifier(run=lambda cmd, **kw: calls.append(cmd), which=lambda _: None)
    notifier.send(_alert())
    (cmd,) = calls
    assert cmd[0] == "osascript"
    # El texto va como argumentos, nunca dentro del script AppleScript.
    assert cmd[-2:] == ['Reunión "X"', "Daily · 13:00"]
    assert all('Reunión "X"' not in part for part in cmd[:-2])


# --- configuración [watch] -------------------------------------------------------

ACCOUNT = '[accounts.p]\ncredentials_file = "c.json"\n'


def _load(tmp_path, extra=""):
    path = tmp_path / "accounts.toml"
    path.write_text(ACCOUNT + extra, encoding="utf-8")
    return load_config(path)


def test_watch_por_defecto(tmp_path):
    assert _load(tmp_path).watch == WatchConfig(reminders=(10, 1), stale_after_minutes=15)


def test_watch_personalizado(tmp_path):
    cfg = _load(tmp_path, "[watch]\nreminders = [15, 5, 1]\nstale_after_minutes = 30\n")
    assert cfg.watch == WatchConfig(reminders=(15, 5, 1), stale_after_minutes=30)


@pytest.mark.parametrize(
    "extra",
    ["[watch]\nreminders = []\n", "[watch]\nreminders = [0]\n", "[watch]\nreminders = ['10']\n"],
)
def test_watch_reminders_invalidos(tmp_path, extra):
    with pytest.raises(
        ConfigError, match="watch.reminders debe ser una lista de minutos positivos"
    ):
        _load(tmp_path, extra)


def test_watch_stale_invalido(tmp_path):
    with pytest.raises(ConfigError, match="watch.stale_after_minutes debe ser un entero positivo"):
        _load(tmp_path, "[watch]\nstale_after_minutes = -1\n")


# --- main ------------------------------------------------------------------------


def test_main_once(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "accounts.toml"
    cfg.write_text(ACCOUNT, encoding="utf-8")
    db = tmp_path / "c.db"
    store = Store(db)
    start = datetime.now(UTC) + timedelta(seconds=30)
    store.replace_account_events("p", [_event("p", "a", start)], synced_at=datetime.now(UTC))
    store.close()
    notifier = FakeNotifier()
    monkeypatch.setattr(watch, "build_notifiers", lambda config: [notifier])

    code = watch.main(["--config", str(cfg), "--db", str(db), "--once"])

    assert code == 0
    assert [a.title for a in notifier.sent] == ["Reunión en 1 min"]
    assert "[reminder] Reunión en 1 min — Kickoff" in capsys.readouterr().out


def test_main_config_invalida(tmp_path, capsys):
    code = watch.main(
        ["--config", str(tmp_path / "no.toml"), "--db", str(tmp_path / "c.db"), "--once"]
    )
    assert code == 2
    assert (
        "Error de configuración: No se encontró el archivo de configuración"
        in capsys.readouterr().err
    )
    assert not (tmp_path / "c.db").exists()


# --- launchd ---------------------------------------------------------------------


def test_launchd_genera_los_dos_plists(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "accounts.toml"
    cfg.write_text(ACCOUNT, encoding="utf-8")
    monkeypatch.setattr(watch.shutil, "which", lambda name: f"/opt/bin/{name}")
    monkeypatch.setenv("PATH", "/opt/bin:/usr/bin")
    out = tmp_path / "plists"
    logs = tmp_path / "logs"

    code = watch.main(
        [
            "launchd",
            "--config",
            str(cfg),
            "--db",
            "/data/c.db",
            "--output-dir",
            str(out),
            "--project-dir",
            "/repo",
            "--log-dir",
            str(logs),
        ]
    )

    assert code == 0
    sync = plistlib.loads((out / "com.calendar-tool.sync.plist").read_bytes())
    assert sync["Label"] == "com.calendar-tool.sync"
    assert sync["ProgramArguments"] == [
        "/opt/bin/uv",
        "run",
        "--directory",
        "/repo",
        "calendar-tool",
        "sync",
        "--config",
        str(cfg),
        "--db",
        "/data/c.db",
    ]
    assert sync["StartInterval"] == 120
    assert sync["RunAtLoad"] is True
    assert sync["EnvironmentVariables"] == {"PATH": "/opt/bin:/usr/bin"}
    assert sync["StandardErrorPath"] == str(logs / "sync.log")

    watcher = plistlib.loads((out / "com.calendar-tool.watch.plist").read_bytes())
    assert watcher["ProgramArguments"] == [
        "/opt/bin/uv",
        "run",
        "--directory",
        "/repo",
        "calendar-watch",
        "--config",
        str(cfg),
        "--db",
        "/data/c.db",
    ]
    assert watcher["KeepAlive"] is True
    assert "StartInterval" not in watcher
    assert logs.is_dir()
    printed = capsys.readouterr().out
    assert (
        "launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.calendar-tool.watch.plist"
        in printed
    )


def test_launchd_sin_config_existente(tmp_path, capsys):
    code = watch.main(
        ["launchd", "--config", str(tmp_path / "no.toml"), "--output-dir", str(tmp_path / "o")]
    )
    assert code == 2
    assert "Error de configuración" in capsys.readouterr().err
    assert not (tmp_path / "o").exists()
