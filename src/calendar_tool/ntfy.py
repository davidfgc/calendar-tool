"""Notificador ntfy: publica los avisos en un canal que la app de Android recibe.

El nombre del canal es la única protección en ntfy.sh público (quien lo conozca puede
leer los mensajes), así que se exige que sea largo y vive solo en la configuración.
Se publica como JSON para que títulos con acentos o emojis lleguen intactos.
"""

from __future__ import annotations

import json
import re
import urllib.request

from .alerts import Alert

DEFAULT_SERVER = "https://ntfy.sh"
_TOPIC = re.compile(r"[A-Za-z0-9_-]{20,64}")
_TAGS = {"reminder": "calendar", "conflict": "warning", "stale": "rotating_light"}


def validate_topic(topic: str) -> None:
    if not isinstance(topic, str) or not _TOPIC.fullmatch(topic):
        raise ValueError(
            "notify.ntfy.topic debe tener al menos 20 caracteres (máximo 64) de "
            "[A-Za-z0-9_-]: es lo único que protege el canal"
        )


class NtfyNotifier:
    def __init__(self, topic: str, server: str = DEFAULT_SERVER, urlopen=urllib.request.urlopen):
        validate_topic(topic)
        self._topic = topic
        self._url = server.rstrip("/") + "/"
        self._urlopen = urlopen

    def send(self, alert: Alert) -> None:
        payload = {
            "topic": self._topic,
            "title": alert.title,
            "message": alert.message,
            "priority": alert.priority,
            "tags": [_TAGS.get(alert.kind, "bell")],
        }
        if alert.link:
            payload["click"] = alert.link
            payload["actions"] = [{"action": "view", "label": "Unirme", "url": alert.link}]
        request = urllib.request.Request(
            self._url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # urlopen lanza HTTPError ante respuestas 4xx/5xx.
        with self._urlopen(request, timeout=10):
            pass
