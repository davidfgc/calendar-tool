"""`calendar-tool sync`: guarda en SQLite los eventos de las próximas horas.

Pensado para ejecutarse sin interacción (p. ej. desde launchd): nunca abre el
navegador. Una cuenta que necesite reautenticación queda registrada con su error y
`calendar-watch` avisará si lleva demasiado tiempo sin actualizarse.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import ConfigError, load_config
from .fetch import fetch_accounts
from .store import DEFAULT_DB, Store

DEFAULT_HOURS = 48


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("debe ser un entero positivo")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="calendar-tool sync",
        description=(
            "Guarda en SQLite los eventos de las próximas horas de todas las cuentas, "
            "sin abrir nunca el navegador."
        ),
    )
    parser.add_argument(
        "--config", default="accounts.toml", help="Archivo de cuentas (por defecto: accounts.toml)."
    )
    parser.add_argument(
        "--db", default=str(DEFAULT_DB), help=f"Base de datos (por defecto: {DEFAULT_DB})."
    )
    parser.add_argument(
        "--hours",
        type=_positive_int,
        default=DEFAULT_HOURS,
        help=f"Horas hacia adelante a guardar (por defecto: {DEFAULT_HOURS}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2

    tz = ZoneInfo(config.timezone) if config.timezone else datetime.now().astimezone().tzinfo
    now = datetime.now(tz)
    results = fetch_accounts(
        config.accounts,
        time_min=now,
        time_max=now + timedelta(hours=args.hours),
        tz=tz,
        allow_interactive=False,
    )

    store = Store(args.db)
    try:
        store.retain_accounts([a.name for a in config.accounts])
        for result in results:
            if result.error:
                store.record_failure(result.account, result.error, attempted_at=now)
            else:
                store.replace_account_events(result.account, result.events, synced_at=now)
    finally:
        store.close()

    failed = [r for r in results if r.error]
    saved = sum(len(r.events) for r in results)
    print(
        f"Cuentas sincronizadas: {len(results) - len(failed)} | con error: {len(failed)}",
        file=sys.stderr,
    )
    for r in failed:
        print(f"  ⚠ {r.account}: {r.error}", file=sys.stderr)
    print(f"Eventos guardados: {saved}", file=sys.stderr)
    print(f"Base de datos: {store.path}", file=sys.stderr)
    return 1 if failed else 0
