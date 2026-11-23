"""Modelos de dominio de calendar_tool, independientes de la API de Google."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CalendarRef:
    """Referencia a un calendario concreto dentro de una cuenta."""

    account: str
    calendar_id: str
    summary: str = ""


@dataclass(slots=True)
class Account:
    """Una cuenta de Google declarada en la configuración."""

    name: str
    credentials_file: str | None = None
    token_file: str | None = None
    service_account_file: str | None = None
    subject: str | None = None
    calendars: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    """Evento de calendario normalizado, con su cuenta y calendario de origen."""

    account: str
    calendar_id: str
    event_id: str
    title: str
    start: datetime
    end: datetime
    all_day: bool = False
    event_type: str = "default"
    location: str = ""
    hangout_link: str = ""
    attendees: tuple[str, ...] = ()
    # Identificador compartido entre las copias de la misma reunión en distintas cuentas.
    ical_uid: str = ""
    # Respuesta del propio usuario: accepted | declined | tentative | needsAction | "".
    response_status: str = ""
    # "opaque" = ocupado; "transparent" = disponible.
    transparency: str = "opaque"
    # Mejor enlace para unirse (Meet, Zoom, Teams…), o "" si no hay.
    conference_link: str = ""
    updated: str = ""
