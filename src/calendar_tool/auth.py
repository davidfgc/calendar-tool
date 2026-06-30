"""Autenticación de solo lectura para Google Calendar, con caché de token por cuenta.

Las dependencias de Google se importan de forma perezosa (dentro de las funciones)
para que el resto del paquete y los tests no requieran tenerlas instaladas.
"""

from __future__ import annotations

from pathlib import Path

from .models import Account

# Scope de SOLO LECTURA. No se solicita ningún permiso de escritura.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class AuthError(Exception):
    """No se pudieron obtener credenciales para una cuenta."""


class ReauthRequired(AuthError):
    """La cuenta requiere un nuevo consentimiento interactivo del usuario."""


def credentials_for_account(account: Account, *, allow_interactive: bool = True):
    """Devuelve credenciales de solo lectura para la cuenta indicada.

    - Si la cuenta define ``service_account_file``, usa una cuenta de servicio
      (opcionalmente con delegación de dominio vía ``subject``).
    - En caso contrario, usa OAuth de usuario (installed-app) con caché de token.
    """
    if account.service_account_file:
        return _service_account_credentials(account)
    return _user_oauth_credentials(account, allow_interactive=allow_interactive)


def _service_account_credentials(account: Account):
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_file(
        account.service_account_file, scopes=SCOPES
    )
    if account.subject:
        creds = creds.with_subject(account.subject)
    return creds


def _user_oauth_credentials(account: Account, *, allow_interactive: bool):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not account.credentials_file:
        raise AuthError(f"La cuenta '{account.name}' no define 'credentials_file'.")

    token_path = Path(account.token_file) if account.token_file else None

    creds = None
    if token_path and token_path.is_file():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as exc:  # token revocado/caducado sin refresh válido
            raise ReauthRequired(
                f"La cuenta '{account.name}' requiere reautenticación: {exc}"
            ) from exc
        _save_token(token_path, creds)
        return creds

    if not allow_interactive:
        raise ReauthRequired(
            f"La cuenta '{account.name}' requiere consentimiento interactivo "
            "(ejecuta sin --no-interactive para autorizarla)."
        )

    cred_path = Path(account.credentials_file)
    if not cred_path.is_file():
        raise AuthError(
            f"No se encontró el archivo de credenciales de la cuenta '{account.name}': {cred_path}"
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(token_path, creds)
    return creds


def _save_token(token_path: Path | None, creds) -> None:
    if token_path is None:
        return
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
