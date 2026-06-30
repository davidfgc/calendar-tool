"""Carga y validación de la configuración multi-cuenta (accounts.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .models import Account

DEFAULT_OUTPUT_FORMAT = "json"
VALID_FORMATS = ("json", "csv")


class ConfigError(Exception):
    """La configuración está ausente o es inválida."""


@dataclass
class Config:
    accounts: list[Account]
    timezone: str | None = None
    output_format: str = DEFAULT_OUTPUT_FORMAT


def _expand(path: str | None) -> str | None:
    return str(Path(path).expanduser()) if path else None


def load_config(path: str | Path) -> Config:
    """Lee y valida el archivo de cuentas. Lanza ConfigError si algo no cuadra."""
    config_path = Path(path).expanduser()
    if not config_path.is_file():
        raise ConfigError(f"No se encontró el archivo de configuración: {config_path}")

    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Configuración TOML inválida en {config_path}: {exc}") from exc

    accounts_table = data.get("accounts")
    if not isinstance(accounts_table, dict) or not accounts_table:
        raise ConfigError(
            "La configuración debe declarar al menos una cuenta en [accounts.<nombre>]."
        )

    accounts: list[Account] = []
    for name, raw in accounts_table.items():
        if not isinstance(raw, dict):
            raise ConfigError(f"La cuenta '{name}' debe ser una tabla [accounts.{name}].")
        account = Account(
            name=name,
            credentials_file=_expand(raw.get("credentials_file")),
            token_file=_expand(raw.get("token_file")),
            service_account_file=_expand(raw.get("service_account_file")),
            subject=raw.get("subject"),
            calendars=list(raw.get("calendars", [])),
        )
        if not account.credentials_file and not account.service_account_file:
            raise ConfigError(
                f"La cuenta '{name}' necesita 'credentials_file' o 'service_account_file'."
            )
        if account.credentials_file and not account.token_file:
            account.token_file = _expand(f"tokens/{name}.json")
        accounts.append(account)

    output_format = data.get("output_format", DEFAULT_OUTPUT_FORMAT)
    if output_format not in VALID_FORMATS:
        raise ConfigError(f"output_format inválido: {output_format!r} (use 'json' o 'csv').")

    return Config(
        accounts=accounts,
        timezone=data.get("timezone"),
        output_format=output_format,
    )
