"""Fixtures compartidas: zona horaria y reloj fijo para tests deterministas."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

TZ = ZoneInfo("America/Los_Angeles")


@pytest.fixture
def tz():
    return TZ


@pytest.fixture
def now():
    # Reloj fijo: 2026-06-29, 12:00 hora de Los Ángeles.
    return datetime(2026, 6, 29, 12, 0, tzinfo=TZ)
