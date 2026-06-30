"""Escritores de la salida combinada: JSON y CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import CalendarEvent

ATTENDEE_SEPARATOR = ";"
CSV_FIELDS = [
    "start",
    "end",
    "title",
    "all_day",
    "event_type",
    "account",
    "calendar_id",
    "location",
    "hangout_link",
    "attendees",
]


def event_to_dict(event: CalendarEvent) -> dict:
    """Representación serializable de un evento, con su origen (cuenta/calendario)."""
    return {
        "start": event.start.isoformat(),
        "end": event.end.isoformat(),
        "title": event.title,
        "all_day": event.all_day,
        "event_type": event.event_type,
        "account": event.account,
        "calendar_id": event.calendar_id,
        "location": event.location,
        "hangout_link": event.hangout_link,
        "attendees": list(event.attendees),
        "event_id": event.event_id,
    }


def write_json(events: list[CalendarEvent], path: str | Path) -> None:
    payload = [event_to_dict(e) for e in events]
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(events: list[CalendarEvent], path: str | Path) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for event in events:
            writer.writerow(
                {
                    "start": event.start.isoformat(),
                    "end": event.end.isoformat(),
                    "title": event.title,
                    "all_day": event.all_day,
                    "event_type": event.event_type,
                    "account": event.account,
                    "calendar_id": event.calendar_id,
                    "location": event.location,
                    "hangout_link": event.hangout_link,
                    "attendees": ATTENDEE_SEPARATOR.join(event.attendees),
                }
            )


def write_events(events: list[CalendarEvent], path: str | Path, fmt: str) -> None:
    """Escribe los eventos en el formato indicado ('json' o 'csv')."""
    if fmt == "json":
        write_json(events, path)
    elif fmt == "csv":
        write_csv(events, path)
    else:
        raise ValueError(f"Formato de salida no soportado: {fmt!r}")
