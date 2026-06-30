# TECH_STACK

Contexto técnico del proyecto **calendar-tool**, para uso de los asistentes de
código (Spec → Plan → Tasks → código). Mantén este archivo actualizado cuando se
tomen nuevas decisiones técnicas.

## Resumen del proyecto

Herramienta de línea de comandos (script) que se conecta **en modo solo lectura**
a calendarios de Google —de varias cuentas (personal, trabajo, cliente) y varios
calendarios dentro de cada una— para obtener los eventos de hoy aún pendientes y
volcarlos a un archivo (JSON/CSV). Ver `docs/specs/` para el detalle de producto.

## Stack base (decidido)

* **Lenguaje**: Python 3.12+
* **Gestor de dependencias y entornos**: [uv](https://docs.astral.sh/uv/)
  * El proyecto se define en `pyproject.toml`; el lockfile es `uv.lock`.
  * Dependencias: `uv add <paquete>`. Entorno/instalación: `uv sync`.
  * Ejecutar comandos dentro del entorno: `uv run <comando>`.
  * **No** usar `pip`/`venv`/`poetry` directamente; todo pasa por `uv`.

## Convenciones (por defecto, ajustables en el Plan)

* **Layout del paquete**: código fuente bajo `src/` (layout `src/`), con el
  paquete principal en `src/calendar_tool/`. Punto de entrada CLI definido en
  `pyproject.toml` (`[project.scripts]`).
* **Estilo y linting**: [Ruff](https://docs.astral.sh/ruff/) para lint + formato.
* **Tipado**: type hints en todo el código; comprobación con un type checker
  (p. ej. `mypy` o `ty`/`pyright`) — a confirmar en el Plan.
* **Tests**: `pytest`, en `tests/`, archivos `test_*.py`. Las dependencias
  externas (API de Google, red, reloj/zona horaria) se aíslan con *fakes*/mocks.
* **Configuración**: parámetros vía flags de CLI y/o archivo de configuración +
  variables de entorno. **Nunca** hardcodear credenciales ni rutas de secretos.

## Por decidir en el Plan (`/plan-iaexpert`)

Estas piezas dependen de la funcionalidad y se concretan al planificar; aquí
quedan como candidatas, no como decisiones cerradas:

* **Cliente de Google Calendar**: candidatas `google-api-python-client` +
  `google-auth` / `google-auth-oauthlib` (lectura vía Calendar API v3).
* **Modelo de autenticación / multi-cuenta**: OAuth de usuario (instalado) con
  scope **solo lectura** (`calendar.readonly` / `calendar.events.readonly`).
  Tener en cuenta que **las cuentas de trabajo y de cliente pueden tener
  restricciones** de organización (consentimiento, apps no verificadas, acceso
  delegado), lo que puede condicionar el método de credenciales por cuenta.
* **Persistencia de tokens** por cuenta y **formato de salida** (JSON/CSV).
* **Manejo de zonas horarias** (criterio de "hoy" y "ya pasó").

## Seguridad (no negociable)

* Acceso a Google **exclusivamente de solo lectura**: jamás solicitar scopes de
  escritura ni crear/modificar/eliminar eventos.
* Credenciales y tokens **fuera del control de versiones** (añadir a
  `.gitignore`); nunca registrarlos en logs ni en la salida.
