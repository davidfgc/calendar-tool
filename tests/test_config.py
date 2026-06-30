"""Tests de la carga y validación de la configuración multi-cuenta."""

from __future__ import annotations

import pytest

from calendar_tool.config import ConfigError, load_config


def write_cfg(tmp_path, text: str):
    path = tmp_path / "accounts.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_carga_minima(tmp_path):
    cfg = write_cfg(
        tmp_path,
        """
[accounts.personal]
credentials_file = "creds.json"
token_file = "tok.json"
""",
    )
    config = load_config(cfg)
    assert len(config.accounts) == 1
    assert config.accounts[0].name == "personal"
    assert config.output_format == "json"


def test_token_por_defecto_si_falta(tmp_path):
    cfg = write_cfg(
        tmp_path,
        """
[accounts.personal]
credentials_file = "creds.json"
""",
    )
    config = load_config(cfg)
    assert config.accounts[0].token_file is not None
    assert "personal" in config.accounts[0].token_file


def test_archivo_inexistente(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.toml")


def test_cuenta_sin_credenciales(tmp_path):
    cfg = write_cfg(tmp_path, "[accounts.personal]\n")
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_sin_cuentas(tmp_path):
    cfg = write_cfg(tmp_path, 'output_format = "json"\n')
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_formato_invalido(tmp_path):
    cfg = write_cfg(
        tmp_path,
        """
output_format = "xml"
[accounts.personal]
credentials_file = "creds.json"
""",
    )
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_service_account_valida(tmp_path):
    cfg = write_cfg(
        tmp_path,
        """
[accounts.cliente]
service_account_file = "sa.json"
subject = "me@cliente.com"
""",
    )
    config = load_config(cfg)
    assert config.accounts[0].service_account_file is not None
    assert config.accounts[0].subject == "me@cliente.com"
