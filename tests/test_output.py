"""Tests de los escritores de salida JSON y CSV."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from calendar_tool.models import CalendarEvent
from calendar_tool.output import write_csv, write_json

TZ = ZoneInfo("America/Los_Angeles")


def make_event(**kw) -> CalendarEvent:
    base = dict(
        account="personal",
        calendar_id="primary",
        event_id="1",
        title="Reunión",
        start=datetime(2026, 6, 29, 13, tzinfo=TZ),
        end=datetime(2026, 6, 29, 14, tzinfo=TZ),
        attendees=("a@x.com", "b@x.com"),
    )
    base.update(kw)
    return CalendarEvent(**base)


def test_write_json_incluye_origen_y_asistentes(tmp_path):
    out = tmp_path / "events.json"
    write_json([make_event()], out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data[0]["title"] == "Reunión"
    assert data[0]["account"] == "personal"
    assert data[0]["calendar_id"] == "primary"
    assert data[0]["attendees"] == ["a@x.com", "b@x.com"]


def test_write_csv_aplana_asistentes(tmp_path):
    out = tmp_path / "events.csv"
    write_csv([make_event()], out)
    rows = list(csv.DictReader(out.read_text(encoding="utf-8").splitlines()))
    assert rows[0]["attendees"] == "a@x.com;b@x.com"
    assert rows[0]["title"] == "Reunión"
    assert rows[0]["account"] == "personal"


def test_write_json_lista_vacia(tmp_path):
    out = tmp_path / "events.json"
    write_json([], out)
    assert json.loads(out.read_text(encoding="utf-8")) == []
