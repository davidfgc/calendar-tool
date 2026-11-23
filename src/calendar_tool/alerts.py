"""Planificador de avisos de calendar-watch.

Código puro: recibe las reuniones ya consolidadas, el estado de sincronización, el
reloj y qué claves ya se enviaron, y devuelve los avisos a mandar. Cada aviso lleva las
claves (``marks``) que hay que registrar como enviadas para no repetirlo.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo

from .consolidate import Meeting
from .events import WORKING_LOCATION
from .store import SyncStatus

OUT_OF_OFFICE = "outOfOffice"
_NOT_MEETINGS = {WORKING_LOCATION, OUT_OF_OFFICE}
_MAX_ERROR = 160


@dataclass(frozen=True, slots=True)
class Alert:
    kind: str  # reminder | conflict | stale
    title: str
    message: str
    marks: tuple[str, ...]
    link: str = ""
    priority: int = 3  # 1 (mínima) .. 5 (urgente), como ntfy


def _is_meeting(m: Meeting) -> bool:
    e = m.event
    return not e.all_day and e.event_type not in _NOT_MEETINGS and e.response_status != "declined"


def _is_busy(m: Meeting) -> bool:
    return _is_meeting(m) and m.event.transparency != "transparent"


def _meeting_key(m: Meeting) -> str:
    e = m.event
    uid = e.ical_uid or f"{e.account}/{e.calendar_id}/{e.event_id}"
    return f"{uid}@{int(e.start.timestamp())}"


def _when(dt: datetime, now: datetime, tz: tzinfo) -> str:
    local = dt.astimezone(tz)
    if local.date() != now.astimezone(tz).date():
        return local.strftime("%d/%m %H:%M")
    return local.strftime("%H:%M")


def _reminders(meetings, now, offsets, is_sent, tz) -> list[Alert]:
    alerts = []
    for m in meetings:
        start = m.event.start
        if not _is_meeting(m) or start <= now:
            continue
        passed = [o for o in sorted(offsets) if now >= start - timedelta(minutes=o)]
        if not passed:
            continue
        key = _meeting_key(m)
        marks = tuple(f"reminder:{key}:{o}" for o in passed)
        if is_sent(marks[0]):  # el más urgente ya se avisó
            continue
        minutes = max(1, math.ceil((start - now).total_seconds() / 60))
        alerts.append(
            Alert(
                kind="reminder",
                title=f"Reunión en {minutes} min",
                message=f"{m.event.title} · {_when(start, now, tz)} · {', '.join(m.accounts)}",
                marks=marks,
                link=m.event.conference_link,
                priority=5 if passed[0] <= 1 else 4,
            )
        )
    return alerts


def _describe(m: Meeting, now, tz) -> str:
    e = m.event
    span = f"{_when(e.start, now, tz)}–{e.end.astimezone(tz):%H:%M}"
    return f"{e.title} ({span}, {', '.join(m.accounts)})"


def _conflicts(meetings, now, is_sent, tz) -> list[Alert]:
    busy = sorted(
        (m for m in meetings if _is_busy(m) and m.event.end > now), key=lambda m: m.event.start
    )
    alerts = []
    for i, a in enumerate(busy):
        for b in busy[i + 1 :]:
            if b.event.start >= a.event.end:
                break  # ordenadas por inicio: ninguna posterior se solapa con a
            key = "conflict:" + "|".join(sorted((_meeting_key(a), _meeting_key(b))))
            if is_sent(key):
                continue
            alerts.append(
                Alert(
                    kind="conflict",
                    title="Conflicto de reuniones",
                    message=f"{_describe(a, now, tz)} se solapa con {_describe(b, now, tz)}",
                    marks=(key,),
                    priority=4,
                )
            )
    return alerts


def _stale(statuses: list[SyncStatus], now, stale_after, is_sent, tz) -> list[Alert]:
    if not statuses:
        key = "stale:none"
        if is_sent(key):
            return []
        message = "No hay datos de sincronización: ¿está corriendo calendar-tool sync?"
        return [Alert("stale", "Calendario sin actualizar", message, (key,))]

    alerts = []
    for s in statuses:
        if s.last_success is not None and now - s.last_success <= stale_after:
            continue
        since = int(s.last_success.timestamp()) if s.last_success else "never"
        key = f"stale:{s.account}:{since}"
        if is_sent(key):
            continue
        if s.last_success is None:
            text = f"La cuenta '{s.account}' nunca se ha sincronizado"
        else:
            when = _when(s.last_success, now, tz)
            article = "las" if "/" not in when else "el"
            text = f"La cuenta '{s.account}' no se actualiza desde {article} {when}"
        if s.last_error:
            error = (
                s.last_error if len(s.last_error) <= _MAX_ERROR else s.last_error[:_MAX_ERROR] + "…"
            )
            text += f" ({error})"
        text += f". Vuelve a iniciar sesión: uv run calendar-tool --account {s.account}"
        alerts.append(Alert("stale", "Calendario sin actualizar", text, (key,)))
    return alerts


def plan_alerts(
    meetings: Iterable[Meeting],
    statuses: list[SyncStatus],
    now: datetime,
    *,
    reminders: Iterable[int],
    stale_after: timedelta,
    is_sent: Callable[[str], bool],
    tz: tzinfo,
) -> list[Alert]:
    """Avisos pendientes: cuentas sin actualizar, conflictos y recordatorios."""
    meetings = list(meetings)
    return (
        _stale(statuses, now, stale_after, is_sent, tz)
        + _conflicts(meetings, now, is_sent, tz)
        + _reminders(meetings, now, tuple(reminders), is_sent, tz)
    )
