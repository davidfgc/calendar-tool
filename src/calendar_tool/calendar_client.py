"""Wrapper de solo lectura sobre la API de Google Calendar v3.

Define un Protocol (``CalendarClient``) que es lo único que necesita la lógica de
eventos; así los tests pueden sustituirlo por un doble sin red.
"""

from __future__ import annotations

from typing import Protocol

from .models import CalendarRef


class CalendarClient(Protocol):
    """Interfaz mínima que consume la lógica de eventos."""

    account: str

    def list_calendars(self) -> list[CalendarRef]: ...

    def list_raw_events(self, calendar_id: str, time_min: str, time_max: str) -> list[dict]: ...


class GoogleCalendarClient:
    """Implementación real contra la API de Google Calendar."""

    def __init__(self, service, account: str) -> None:
        self._service = service
        self.account = account

    @classmethod
    def from_credentials(cls, credentials, account: str) -> GoogleCalendarClient:
        from googleapiclient.discovery import build

        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        return cls(service, account)

    def list_calendars(self) -> list[CalendarRef]:
        refs: list[CalendarRef] = []
        page_token = None
        while True:
            resp = self._service.calendarList().list(pageToken=page_token).execute()
            for item in resp.get("items", []):
                refs.append(
                    CalendarRef(
                        account=self.account,
                        calendar_id=item["id"],
                        summary=item.get("summary", ""),
                    )
                )
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return refs

    def list_raw_events(self, calendar_id: str, time_min: str, time_max: str) -> list[dict]:
        events: list[dict] = []
        page_token = None
        while True:
            resp = (
                self._service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    pageToken=page_token,
                )
                .execute()
            )
            events.extend(resp.get("items", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return events
