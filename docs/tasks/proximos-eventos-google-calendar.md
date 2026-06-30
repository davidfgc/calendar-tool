# Tasks: Lector de próximos eventos de hoy de calendarios de Google

## Fase 1: Setup / Fundacional
<!-- Tareas transversales que bloquean a las Historias (proyecto, deps, andamiaje) -->
* [ ] **[Setup]** Crear `pyproject.toml` con metadata del proyecto (Python 3.12+), configuración de Ruff y el script de CLI en `[project.scripts]` (Decisión 6).
* [ ] **[Setup]** Añadir las dependencias de runtime con `uv add` (`google-api-python-client`, `google-auth-oauthlib`, `google-auth`) y generar `uv.lock`.
* [ ] **[Setup]** Añadir las dependencias de desarrollo con `uv add --dev` (`pytest`, `ruff`).
* [ ] **[Setup]** Crear `.gitignore` excluyendo `tokens/`, `*credentials*.json` y los archivos de salida (requisito de seguridad del Plan).
* [ ] **[Setup]** Crear el marcador de paquete `src/calendar_tool/__init__.py`.
* [ ] **[Setup]** Crear `README.md` con las instrucciones de configuración de OAuth (consola de Google) y el uso básico del CLI.
---

## Fase 2: Historia 1 - Ver los próximos eventos de hoy de un calendario (MVP)
<!-- Conexión solo lectura a UN calendario → eventos pendientes de hoy → archivo -->
* [ ] **[Historia 1]** Crear `src/calendar_tool/models.py` con el dataclass `CalendarEvent` (inicio, fin, título, ubicación/enlace, asistentes y campos de origen cuenta/calendario).
* [ ] **[Historia 1]** Crear `src/calendar_tool/auth.py`: flujo OAuth installed-app con scope `calendar.readonly` y caché de token en disco para una credencial (Decisión 1).
* [ ] **[Historia 1]** Crear `src/calendar_tool/calendar_client.py`: wrapper sobre Calendar API que liste los eventos de un calendario (`events().list` con `timeMin`/`timeMax` del día, `singleEvents=True`, `orderBy=startTime`).
* [ ] **[Historia 1]** Crear `src/calendar_tool/events.py`: función que filtre los eventos cuya hora de fin sea posterior a "ahora" (incluye en curso) y los mapee a `CalendarEvent` (Decisión 4).
* [ ] **[Historia 1]** Crear `src/calendar_tool/output.py`: escritores que serialicen una lista de `CalendarEvent` a JSON y a CSV (aplanando asistentes), seleccionable por formato (Decisión 5).
* [ ] **[Historia 1]** Crear `src/calendar_tool/cli.py`: orquestar auth → fetch → filtro → salida para un calendario, con flags (credencial, id de calendario, formato y ruta de salida).
* [ ] **[Historia 1]** Crear `src/calendar_tool/__main__.py` para habilitar `python -m calendar_tool`.
* [ ] **[Historia 1 - Test]** Crear `tests/fakes.py` con `FakeCalendarClient` que devuelva eventos sin acceder a la red.
* [ ] **[Historia 1 - Test]** Crear `tests/conftest.py` con fixtures de reloj fijo y configuración de prueba.
* [ ] **[Historia 1 - Test]** Crear `tests/test_events.py` que valide el filtro "fin > ahora", los eventos en curso y el orden por hora de inicio.
* [ ] **[Historia 1 - Test]** Crear `tests/test_output.py` que valide la serialización a JSON y CSV (incluido el aplanado de asistentes).
---

## Fase 3: Historia 2 - Conectar varias cuentas y calendarios (personal, trabajo, cliente)
<!-- Multi-cuenta declarado en config + multi-calendario, con tolerancia a restricciones -->
* [ ] **[Historia 2]** Crear `accounts.example.toml`: plantilla de configuración multi-cuenta (`personal`/`trabajo`/`cliente-x`, `credentials_file`, ruta de token), sin secretos.
* [ ] **[Historia 2]** Crear `src/calendar_tool/config.py`: carga y validación de `accounts.toml` (cuentas, credenciales y rutas de token) (Decisión 2).
* [ ] **[Historia 2]** Modificar `src/calendar_tool/models.py`: añadir los dataclasses `Account` y `CalendarRef`.
* [ ] **[Historia 2]** Modificar `src/calendar_tool/auth.py`: gestionar credenciales y token por cuenta (caché independiente) y, opcionalmente, `service_account` con domain-wide delegation (Decisiones 2 y 3).
* [ ] **[Historia 2]** Modificar `src/calendar_tool/calendar_client.py`: listar los calendarios de una cuenta (`calendarList`) y permitir leer uno, varios o todos.
* [ ] **[Historia 2]** Modificar `src/calendar_tool/cli.py`: seleccionar cuenta(s) y calendario(s) desde la config, aislar los fallos por cuenta y reportar las cuentas que requieren reautenticación (Decisión 3).
* [ ] **[Historia 2 - Test]** Crear `tests/test_config.py` que valide la carga de cuentas y el manejo de configuración inválida.
---

## Fase 4: Historia 3 - Vista combinada y ordenada de todos los calendarios
<!-- Combinar todas las cuentas/calendarios en una sola salida ordenada por hora -->
* [ ] **[Historia 3]** Modificar `src/calendar_tool/events.py`: combinar los eventos de todas las cuentas/calendarios y ordenarlos globalmente por hora de inicio, con desempate estable por hora de fin y luego título (Decisión 4).
* [ ] **[Historia 3]** Modificar `src/calendar_tool/cli.py`: añadir el modo combinado que vuelque todas las cuentas/calendarios en una sola salida ordenada.
* [ ] **[Historia 3]** Modificar `src/calendar_tool/output.py`: asegurar que cada evento de la salida combinada indique su origen (cuenta y calendario).
* [ ] **[Historia 3 - Test]** Modificar `tests/test_events.py`: añadir casos de combinación multi-cuenta, orden global y desempate estable.
---

## Fase 5: Verificación
<!-- Cierre coherente con el stack (uv + Ruff + pytest) -->
* [ ] **[Verificación]** Ejecutar lint y formato: `uv run ruff format . && uv run ruff check --fix .`.
* [ ] **[Verificación]** Ejecutar los tests: `uv run pytest`.
* [ ] **[Verificación]** Prueba manual: correr el CLI contra una cuenta real en solo lectura y confirmar que el archivo de salida contiene solo los eventos pendientes de hoy.
