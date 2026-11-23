"""`calendar-watch`: avisos de reuniones, conflictos y cuentas sin actualizar.

Lee la base SQLite que llena `calendar-tool sync` y notifica en macOS. También genera
los plists de launchd para el arranque automático (no los instala).
"""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime, timedelta, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo

from .alerts import Alert, plan_alerts
from .config import ConfigError, WatchConfig, load_config
from .consolidate import dedupe
from .store import DEFAULT_DB, Store

DEFAULT_INTERVAL = 15
LOOKAHEAD = timedelta(hours=48)
SENT_RETENTION = timedelta(days=3)
SYNC_LABEL = "com.calendar-tool.sync"
WATCH_LABEL = "com.calendar-tool.watch"


def run_cycle(
    store: Store,
    watch_cfg: WatchConfig,
    notifiers: list,
    now: datetime,
    tz: tzinfo,
    log: Callable[[str], None] = print,
) -> list[Alert]:
    """Un ciclo: planifica los avisos pendientes, los envía y los marca como enviados."""
    meetings = dedupe(store.events_between(now, now + LOOKAHEAD))
    alerts = plan_alerts(
        meetings,
        store.sync_status(),
        now,
        reminders=watch_cfg.reminders,
        stale_after=timedelta(minutes=watch_cfg.stale_after_minutes),
        is_sent=store.was_sent,
        tz=tz,
    )
    for alert in alerts:
        for notifier in notifiers:
            try:
                notifier.send(alert)
            except Exception as exc:  # un canal roto no debe bloquear a los demás
                log(f"⚠ {type(notifier).__name__}: {exc}")
        for key in alert.marks:
            store.mark_sent(key, sent_at=now)
        log(
            f"{now.astimezone(tz):%Y-%m-%d %H:%M:%S} [{alert.kind}] {alert.title} — {alert.message}"
        )
    store.prune_sent(before=now - SENT_RETENTION)
    return alerts


class MacNotifier:
    """Notificación de macOS con sonido (terminal-notifier si existe; si no, osascript)."""

    def __init__(self, run=subprocess.run, which=shutil.which) -> None:
        self._run = run
        self._which = which

    def send(self, alert: Alert) -> None:
        tn = self._which("terminal-notifier")
        if tn:
            cmd = [tn, "-title", alert.title, "-message", alert.message, "-sound", "Glass"]
            if alert.link:
                cmd += ["-open", alert.link]
        else:
            # El texto viaja como argumentos, nunca dentro del script AppleScript.
            cmd = [
                "osascript",
                "-e",
                "on run argv",
                "-e",
                "display notification (item 2 of argv) with title (item 1 of argv)"
                ' sound name "Glass"',
                "-e",
                "end run",
                alert.title,
                alert.message,
            ]
        self._run(cmd, check=True, capture_output=True, timeout=10)


def build_notifiers(config) -> list:
    return [MacNotifier()]


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("debe ser un entero positivo")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="calendar-watch",
        description="Avisa de reuniones, conflictos y cuentas sin actualizar (macOS).",
        epilog="Subcomando: 'calendar-watch launchd --help' genera los plists de launchd.",
    )
    parser.add_argument("--config", default="accounts.toml", help="Archivo de cuentas.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Base SQLite de calendar-tool.")
    parser.add_argument(
        "--interval",
        type=_positive_int,
        default=DEFAULT_INTERVAL,
        help=f"Segundos entre ciclos (por defecto {DEFAULT_INTERVAL}).",
    )
    parser.add_argument("--once", action="store_true", help="Ejecuta un solo ciclo y termina.")
    return parser


def build_launchd_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="calendar-watch launchd",
        description="Genera los plists de launchd (sync y watch). No instala nada.",
    )
    parser.add_argument("--config", required=True, help="Archivo de cuentas.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Base SQLite de calendar-tool.")
    parser.add_argument("--output-dir", default="launchd", help="Directorio de salida.")
    parser.add_argument(
        "--sync-interval",
        type=_positive_int,
        default=120,
        help="Segundos entre sincronizaciones (por defecto 120).",
    )
    parser.add_argument(
        "--project-dir",
        default=str(Path(__file__).resolve().parents[2]),
        help="Directorio del proyecto (por defecto, la raíz del repositorio).",
    )
    parser.add_argument(
        "--log-dir",
        default="~/Library/Logs/calendar-tool",
        help="Directorio de logs (por defecto ~/Library/Logs/calendar-tool).",
    )
    return parser


def _resolve_tz(timezone: str | None) -> tzinfo:
    if timezone:
        return ZoneInfo(timezone)
    return datetime.now().astimezone().tzinfo


def _launchd(argv: list[str]) -> int:
    args = build_launchd_parser().parse_args(argv)
    config_path = Path(args.config).expanduser().resolve()
    if not config_path.is_file():
        print(
            f"Error de configuración: No se encontró el archivo de configuración: {config_path}",
            file=sys.stderr,
        )
        return 2
    uv = shutil.which("uv")
    if not uv:
        print("Error: no se encontró 'uv' en el PATH.", file=sys.stderr)
        return 2

    # launchd no arranca en el directorio actual: todas las rutas deben ser absolutas.
    cfg = str(config_path)
    db = str(Path(args.db).expanduser().resolve())
    project = str(Path(args.project_dir).expanduser().resolve())
    log_dir = Path(args.log_dir).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    base_args = [uv, "run", "--directory", project]
    env = {"PATH": os.environ["PATH"]}
    sync = {
        "Label": SYNC_LABEL,
        "ProgramArguments": [*base_args, "calendar-tool", "sync", "--config", cfg, "--db", db],
        "StartInterval": args.sync_interval,
        "RunAtLoad": True,
        "EnvironmentVariables": env,
        "StandardOutPath": str(log_dir / "sync.log"),
        "StandardErrorPath": str(log_dir / "sync.log"),
    }
    watcher = {
        "Label": WATCH_LABEL,
        "ProgramArguments": [*base_args, "calendar-watch", "--config", cfg, "--db", db],
        "KeepAlive": True,
        "RunAtLoad": True,
        "EnvironmentVariables": env,
        "StandardOutPath": str(log_dir / "watch.log"),
        "StandardErrorPath": str(log_dir / "watch.log"),
    }
    written = []
    for label, data in ((SYNC_LABEL, sync), (WATCH_LABEL, watcher)):
        path = output_dir / f"{label}.plist"
        path.write_bytes(plistlib.dumps(data))
        written.append(path)

    print("Plists generados:")
    for path in written:
        print(f"  {path}")
    print(
        f"""
Para instalarlos (decisión tuya; esta herramienta no ejecuta launchctl):

  cp {output_dir}/*.plist ~/Library/LaunchAgents/
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/{SYNC_LABEL}.plist
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/{WATCH_LABEL}.plist

Para detenerlos:

  launchctl bootout gui/$(id -u)/{WATCH_LABEL}
  launchctl bootout gui/$(id -u)/{SYNC_LABEL}

Logs en {log_dir}"""
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["launchd"]:
        return _launchd(argv[1:])
    args = build_parser().parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2

    store = Store(args.db)
    notifiers = build_notifiers(config)
    try:
        while True:
            try:
                tz = _resolve_tz(config.timezone)
                now = datetime.now(tz)
                run_cycle(
                    store, config.watch, notifiers, now, tz, log=lambda s: print(s, flush=True)
                )
            except Exception as exc:
                print(f"⚠ ciclo fallido: {exc}", file=sys.stderr, flush=True)
            if args.once:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 130
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
