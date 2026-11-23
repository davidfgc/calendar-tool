"""Interfaz de línea de comandos de calendar_tool.

Orquesta: resolver cuentas -> autenticar -> obtener eventos -> filtrar pendientes
-> combinar y ordenar -> escribir archivo. Los fallos se aíslan por cuenta: si una
cuenta falla, las demás se entregan igualmente.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import __version__
from .config import Config, ConfigError, load_config
from .events import combine_and_sort, day_bounds, is_pending
from .fetch import AccountResult, fetch_accounts
from .models import Account
from .output import write_events

DEFAULT_CONFIG = "accounts.toml"

__all__ = ["AccountResult", "build_parser", "main", "run"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="calendar-tool",
        description="Obtiene en solo lectura los próximos eventos de hoy de Google Calendar.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config", help=f"Ruta al archivo de cuentas (por defecto: {DEFAULT_CONFIG})."
    )
    parser.add_argument(
        "--account",
        action="append",
        dest="accounts",
        metavar="NOMBRE",
        help="Limita a esta(s) cuenta(s) de la config. Repetible.",
    )
    parser.add_argument(
        "--calendar",
        action="append",
        dest="calendars",
        metavar="ID",
        help="Limita a este(os) calendario(s). Repetible.",
    )
    parser.add_argument(
        "--credentials", help="(Modo simple) archivo OAuth client de una sola cuenta."
    )
    parser.add_argument("--token", help="(Modo simple) archivo de token a usar/crear.")
    parser.add_argument("--format", choices=("json", "csv"), help="Formato de salida.")
    parser.add_argument("--output", "-o", help="Ruta del archivo de salida.")
    parser.add_argument("--timezone", help="Zona horaria IANA (por defecto: la local).")
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="No abrir navegador; falla la cuenta que requiera consentimiento.",
    )
    parser.add_argument(
        "--include-working-location",
        action="store_true",
        help="Incluir las entradas de Ubicación de trabajo (Home/Office), excluidas por defecto.",
    )
    return parser


def _resolve_timezone(name: str | None):
    if name:
        return ZoneInfo(name)
    # Zona horaria local del sistema (offset fijo actual).
    return datetime.now().astimezone().tzinfo


def _accounts_from_args(args) -> tuple[list[Account], Config | None]:
    # Modo simple: una sola cuenta ad-hoc vía --credentials, sin archivo de config.
    if args.credentials and not args.config:
        account = Account(
            name="default",
            credentials_file=str(Path(args.credentials).expanduser()),
            token_file=(
                str(Path(args.token).expanduser()) if args.token else "tokens/default.json"
            ),
            calendars=list(args.calendars or []),
        )
        return [account], None

    # Modo config (multi-cuenta).
    config = load_config(args.config or DEFAULT_CONFIG)
    accounts = config.accounts
    if args.accounts:
        wanted = set(args.accounts)
        found = {a.name for a in accounts}
        missing = wanted - found
        if missing:
            raise ConfigError(f"Cuentas no encontradas en la config: {', '.join(sorted(missing))}")
        accounts = [a for a in accounts if a.name in wanted]
    return accounts, config


def run(args) -> int:
    try:
        accounts, config = _accounts_from_args(args)
    except ConfigError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2

    tz = _resolve_timezone(args.timezone or (config.timezone if config else None))
    now = datetime.now(tz)
    day_start, day_end = day_bounds(now)

    results = fetch_accounts(
        accounts,
        time_min=day_start,
        time_max=day_end,
        tz=tz,
        allow_interactive=not args.no_interactive,
        calendars_override=args.calendars,
        include_working_location=args.include_working_location,
    )
    for result in results:
        result.events = [e for e in result.events if is_pending(e, now)]

    all_events = combine_and_sort([e for r in results for e in r.events])

    fmt = args.format or (config.output_format if config else "json")
    output_path = args.output or f"events-{now:%Y-%m-%d}.{fmt}"
    write_events(all_events, output_path, fmt)

    _print_summary(results, all_events, output_path, fmt)
    return 1 if any(r.error for r in results) else 0


def _print_summary(results, all_events, output_path, fmt) -> None:
    ok = [r for r in results if not r.error]
    failed = [r for r in results if r.error]
    print(f"Cuentas leídas: {len(ok)} | con error: {len(failed)}", file=sys.stderr)
    for r in failed:
        print(f"  ⚠ {r.account}: {r.error}", file=sys.stderr)
    print(f"Eventos pendientes de hoy: {len(all_events)}", file=sys.stderr)
    print(f"Salida ({fmt}): {output_path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.credentials and not args.config and not Path(DEFAULT_CONFIG).is_file():
        parser.error(
            "No hay configuración: usa --config <archivo>, crea ./accounts.toml, "
            "o pasa --credentials <archivo> para el modo simple."
        )
    try:
        return run(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
