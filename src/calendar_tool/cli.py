"""Interfaz de línea de comandos de calendar_tool.

Orquesta: resolver cuentas -> autenticar -> obtener eventos -> filtrar pendientes
-> combinar y ordenar -> escribir archivo. Los fallos se aíslan por cuenta: si una
cuenta falla, las demás se entregan igualmente.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import __version__
from .config import Config, ConfigError, load_config
from .events import collect_events, combine_and_sort, day_bounds, month_bounds
from .models import Account, CalendarEvent, CalendarRef
from .output import write_events

DEFAULT_CONFIG = "accounts.toml"


@dataclass
class AccountResult:
    account: str
    events: list[CalendarEvent] = field(default_factory=list)
    error: str | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="calendar-tool",
        description=(
            "Obtiene en solo lectura eventos de Google Calendar: por defecto los "
            "pendientes de hoy, o todos los del mes actual con --range month."
        ),
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
        "--range",
        choices=("day", "month"),
        default="day",
        help="Rango temporal: 'day' (eventos pendientes de hoy, por defecto) o "
        "'month' (todos los eventos del mes actual).",
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


def _refs_for_account(client, account: Account, calendars_override) -> list[CalendarRef]:
    wanted = calendars_override or account.calendars
    if wanted:
        return [CalendarRef(account=account.name, calendar_id=c) for c in wanted]
    # Sin lista explícita: leer todos los calendarios de la cuenta.
    return client.list_calendars()


def run(args) -> int:
    from .calendar_client import GoogleCalendarClient

    try:
        accounts, config = _accounts_from_args(args)
    except ConfigError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2

    tz = _resolve_timezone(args.timezone or (config.timezone if config else None))
    now = datetime.now(tz)
    is_month = args.range == "month"
    time_min, time_max = month_bounds(now) if is_month else day_bounds(now)
    pending_only = not is_month

    results: list[AccountResult] = []
    for account in accounts:
        try:
            from .auth import credentials_for_account

            creds = credentials_for_account(account, allow_interactive=not args.no_interactive)
            client = GoogleCalendarClient.from_credentials(creds, account.name)
            refs = _refs_for_account(client, account, args.calendars)
            events = collect_events(
                client,
                refs,
                time_min,
                time_max,
                now,
                tz,
                pending_only=pending_only,
                include_working_location=args.include_working_location,
            )
            results.append(AccountResult(account.name, events))
        except Exception as exc:  # aísla el fallo de esta cuenta
            results.append(AccountResult(account.name, error=str(exc)))

    all_events = combine_and_sort([e for r in results for e in r.events])

    fmt = args.format or (config.output_format if config else "json")
    if args.output:
        output_path = args.output
    elif is_month:
        output_path = f"events-{now:%Y-%m}.{fmt}"
    else:
        output_path = f"events-{now:%Y-%m-%d}.{fmt}"
    write_events(all_events, output_path, fmt)

    _print_summary(results, all_events, output_path, fmt, args.range, time_min, time_max)
    return 1 if any(r.error for r in results) else 0


def _print_summary(results, all_events, output_path, fmt, range_, time_min, time_max) -> None:
    ok = [r for r in results if not r.error]
    failed = [r for r in results if r.error]
    if range_ == "month":
        mode_label, count_label = "mes actual", "Eventos del mes"
    else:
        mode_label, count_label = "día actual", "Eventos pendientes de hoy"
    print(
        f"Modo: {mode_label} | ventana: [{time_min.isoformat()}, {time_max.isoformat()})",
        file=sys.stderr,
    )
    print(f"Cuentas leídas: {len(ok)} | con error: {len(failed)}", file=sys.stderr)
    for r in failed:
        print(f"  ⚠ {r.account}: {r.error}", file=sys.stderr)
    print(f"{count_label}: {len(all_events)}", file=sys.stderr)
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
