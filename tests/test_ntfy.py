"""Tests del notificador ntfy (Android y, a través del teléfono, las gafas)."""

from __future__ import annotations

import json

import pytest

from calendar_tool.alerts import Alert
from calendar_tool.ntfy import NtfyNotifier, validate_topic

TOPIC = "cal-7f3k9q2m8x1v4b6n0zt"


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _capture():
    requests = []

    def urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    return requests, urlopen


def test_publica_json_con_titulo_prioridad_y_enlace():
    requests, urlopen = _capture()
    alert = Alert(
        kind="reminder",
        title="Reunión en 1 min",
        message="Daily · 13:00 · trabajo",
        marks=("k",),
        link="https://meet.google.com/x",
        priority=5,
    )
    NtfyNotifier(TOPIC, server="https://ntfy.sh/", urlopen=urlopen).send(alert)

    ((request, timeout),) = requests
    assert request.full_url == "https://ntfy.sh/"
    assert request.get_method() == "POST"
    assert request.get_header("Content-type") == "application/json"
    assert timeout == 10
    assert json.loads(request.data.decode("utf-8")) == {
        "topic": TOPIC,
        "title": "Reunión en 1 min",
        "message": "Daily · 13:00 · trabajo",
        "priority": 5,
        "tags": ["calendar"],
        "click": "https://meet.google.com/x",
        "actions": [{"action": "view", "label": "Unirme", "url": "https://meet.google.com/x"}],
    }


def test_sin_enlace_no_envia_click_ni_acciones():
    requests, urlopen = _capture()
    alert = Alert(
        kind="conflict",
        title="Conflicto de reuniones",
        message="A se solapa con B",
        marks=("k",),
        priority=4,
    )
    NtfyNotifier(TOPIC, urlopen=urlopen).send(alert)
    payload = json.loads(requests[0][0].data.decode("utf-8"))
    assert "click" not in payload and "actions" not in payload
    assert payload["tags"] == ["warning"]


@pytest.mark.parametrize(
    "topic", ["corto", "con espacios en el nombre del canal", "acentuación-ñ-0123456789", ""]
)
def test_canal_invalido(topic):
    with pytest.raises(ValueError, match="al menos 20 caracteres"):
        validate_topic(topic)


def test_canal_valido():
    validate_topic(TOPIC)


# --- configuración [notify.ntfy] y enlace con calendar-watch ----------------------

from calendar_tool import watch  # noqa: E402
from calendar_tool.config import ConfigError, NtfyConfig, load_config  # noqa: E402

ACCOUNT = '[accounts.p]\ncredentials_file = "c.json"\n'


def _load(tmp_path, extra=""):
    path = tmp_path / "accounts.toml"
    path.write_text(ACCOUNT + extra, encoding="utf-8")
    return load_config(path)


def test_sin_ntfy_por_defecto(tmp_path):
    config = _load(tmp_path)
    assert config.ntfy is None
    assert [type(n).__name__ for n in watch.build_notifiers(config)] == ["MacNotifier"]


def test_ntfy_configurado(tmp_path):
    config = _load(tmp_path, f'[notify.ntfy]\ntopic = "{TOPIC}"\n')
    assert config.ntfy == NtfyConfig(topic=TOPIC, server="https://ntfy.sh")
    names = [type(n).__name__ for n in watch.build_notifiers(config)]
    assert names == ["MacNotifier", "NtfyNotifier"]


def test_ntfy_servidor_propio(tmp_path):
    config = _load(
        tmp_path, f'[notify.ntfy]\ntopic = "{TOPIC}"\nserver = "https://ntfy.example.com"\n'
    )
    assert config.ntfy.server == "https://ntfy.example.com"


def test_ntfy_sin_topic(tmp_path):
    with pytest.raises(ConfigError, match="notify.ntfy.topic es obligatorio"):
        _load(tmp_path, '[notify.ntfy]\nserver = "https://ntfy.sh"\n')


def test_ntfy_topic_corto(tmp_path):
    with pytest.raises(ConfigError, match="al menos 20 caracteres"):
        _load(tmp_path, '[notify.ntfy]\ntopic = "calendario"\n')


def _config_file(tmp_path):
    path = tmp_path / "accounts.toml"
    path.write_text(ACCOUNT, encoding="utf-8")
    return path


class _Recorder:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def send(self, alert):
        if self.fail:
            raise RuntimeError("HTTP Error 403: Forbidden")
        self.sent.append(alert)


def test_watch_test_envia_un_aviso_de_prueba(tmp_path, monkeypatch, capsys):
    recorder = _Recorder()
    monkeypatch.setattr(watch, "build_notifiers", lambda config: [recorder])
    db = tmp_path / "c.db"
    code = watch.main(["--config", str(_config_file(tmp_path)), "--db", str(db), "--test"])
    assert code == 0
    (alert,) = recorder.sent
    assert alert.title == "Prueba de calendar-watch"
    assert alert.message == "Si ves esto, los avisos funcionan."
    assert "✓ _Recorder" in capsys.readouterr().out
    assert not db.exists()  # la prueba no toca la base


def test_watch_test_informa_el_canal_que_falla(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(watch, "build_notifiers", lambda config: [_Recorder(fail=True)])
    code = watch.main(["--config", str(_config_file(tmp_path)), "--test"])
    assert code == 1
    assert "✗ _Recorder: HTTP Error 403: Forbidden" in capsys.readouterr().err
