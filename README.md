# calendar-tool

Herramienta de línea de comandos que se conecta **en modo solo lectura** a uno o
varios calendarios de Google —de distintas cuentas (personal, trabajo, cliente) y
de varios calendarios dentro de cada una— para obtener los **eventos de hoy que aún
no han terminado** y volcarlos, combinados y ordenados por hora, a un archivo
(JSON o CSV).

> Solo lectura por diseño: usa el scope `calendar.readonly`. La herramienta nunca
> crea, modifica ni elimina eventos.

## Requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Instalación

```bash
uv sync
```

## Configuración de OAuth (Google Cloud Console)

Para cada cuenta a la que quieras acceder:

1. En [Google Cloud Console](https://console.cloud.google.com/), crea (o reutiliza)
   un proyecto y habilita la **Google Calendar API**.
2. Crea credenciales **OAuth client ID** de tipo **Desktop app** y descarga el JSON.
3. Guarda ese JSON donde apunte `credentials_file` en tu configuración (ver abajo).
4. La primera ejecución abrirá el navegador para que **consientas el acceso de
   solo lectura**; el token resultante se cachea en `token_file` para reusarlo.

> Cuentas de **trabajo / cliente**: pueden tener restricciones de la organización
> (apps no verificadas, consentimiento de admin, bloqueo de OAuth de terceros). Por
> eso cada cuenta puede usar su propio `credentials_file`, o una cuenta de servicio
> con delegación de dominio (`service_account_file` + `subject`).

## Configuración multi-cuenta

Copia la plantilla y edítala:

```bash
cp accounts.example.toml accounts.toml
```

(`accounts.toml` y los tokens/credenciales están en `.gitignore`.)

## Uso

Leer todas las cuentas de la config y volcar los pendientes de hoy:

```bash
uv run calendar-tool --config accounts.toml
```

Opciones útiles:

```bash
# Limitar a cuentas/calendarios concretos
uv run calendar-tool --account trabajo --calendar primary

# Elegir formato y ruta de salida
uv run calendar-tool --format csv --output hoy.csv

# Modo simple, sin config (una sola cuenta ad-hoc)
uv run calendar-tool --credentials creds.json --token tok.json

# Incluir las entradas de "Ubicación de trabajo" (Home/Office), excluidas por defecto
uv run calendar-tool --include-working-location
```

Las entradas de **Ubicación de trabajo** (eventos de todo el día "Home"/"Office",
`eventType: workingLocation`) se **excluyen por defecto** porque no son eventos a los
que se asista; usa `--include-working-location` si las quieres en la salida. Cada
evento del archivo incluye su `event_type` para que puedas distinguirlos.

Si una cuenta falla (token caducado/revocado, restricción de la org, red), las
demás se entregan igualmente y el error se reporta por separado.

## Sincronizar a SQLite (`calendar-tool sync`)

Guarda los eventos de las próximas 48 h de todas las cuentas en una base SQLite
compartida (por defecto `~/.local/share/calendar-tool/calendar.db`). Nunca abre el
navegador, así que puede ejecutarse desde `launchd`:

```bash
uv run calendar-tool sync --config "$PWD/accounts.toml"
uv run calendar-tool sync --config "$PWD/accounts.toml" --hours 24 --db /ruta/calendar.db
```

- Cada ejecución sustituye los eventos de cada cuenta leída con éxito.
- Si una cuenta falla, conserva sus últimos eventos y registra el error y la hora del
  último éxito (tabla `account_sync`); `calendar-watch` avisa si lleva demasiado tiempo
  sin actualizarse.
- Las cuentas que se quitan de la config se olvidan.
- Código de salida: `0` todo bien, `1` alguna cuenta falló, `2` configuración inválida
  (en ese caso no se toca la base).

## Avisos (`calendar-watch`)

Comando aparte que lee la base SQLite (la llena `calendar-tool sync`) y avisa con una
notificación de macOS con sonido:

- **Recordatorios** 10 y 1 minuto antes de cada reunión, con el enlace (Meet/Zoom/Teams)
  cuando existe; al pulsar la notificación se abre (requiere `terminal-notifier`; sin él
  se usa `osascript`).
- **Conflictos** entre reuniones que se solapan, una sola vez por conflicto.
- **Cuenta sin actualizar** si lleva más de 15 min sin sincronizar con éxito.
- Se ignoran: reuniones rechazadas, marcadas como disponibles, de todo el día,
  ubicación de trabajo y fuera de la oficina.

```bash
uv run calendar-watch --config accounts.toml          # bucle (cada 15 s)
uv run calendar-watch --config accounts.toml --once   # un solo ciclo
```

Opciones: `--db`, `--interval SEGUNDOS`, `--once`, `--test` (envía un aviso de prueba por
cada canal y termina). Ajustes opcionales en `accounts.toml`:

```toml
[watch]
reminders = [10, 1]        # minutos antes
stale_after_minutes = 15
```

### Avisos en Android (ntfy)

Instala la app **ntfy** en Android, suscríbete a un canal con un nombre largo y aleatorio
y añádelo a `accounts.toml` (ignorado por git):

```toml
[notify.ntfy]
topic = "cal-xxxxxxxxxxxxxxxxxxxx"   # mínimo 20 caracteres [A-Za-z0-9_-]
# server = "https://ntfy.sh"         # o tu servidor propio
```

```bash
python3 -c "import secrets; print('cal-' + secrets.token_urlsafe(18))"  # generar un nombre
uv run calendar-watch --config accounts.toml --test                     # comprobar
```

> En `ntfy.sh` público, cualquiera que conozca el nombre del canal puede leer los avisos,
> que incluyen el título de cada reunión. Por eso el nombre debe ser largo y secreto.

El aviso de 1 min llega con prioridad urgente y un botón **Unirme** con el enlace. Si
la app de tus gafas replica las notificaciones del teléfono, también los recibirá.

### Arranque automático con launchd

`sync` cada 2 min y `watch` siempre encendido. Genera los plists (no instala nada):

```bash
uv run calendar-watch launchd --config accounts.toml   # escribe launchd/*.plist
cp launchd/*.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.calendar-tool.sync.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.calendar-tool.watch.plist
```

Para detenerlos: `launchctl bootout gui/$(id -u)/com.calendar-tool.watch` (y `.sync`).
Los logs quedan en `~/Library/Logs/calendar-tool/`.

## Desarrollo

```bash
uv run ruff format . && uv run ruff check --fix .
uv run pytest
```
