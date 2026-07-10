# calendar-tool

Herramienta de línea de comandos que se conecta **en modo solo lectura** a uno o
varios calendarios de Google —de distintas cuentas (personal, trabajo, cliente) y
de varios calendarios dentro de cada una— y vuelca los eventos, combinados y
ordenados por hora, a un archivo (JSON o CSV). Por defecto muestra los **eventos de
hoy que aún no han terminado**; con `--range month` muestra **todos los eventos del
mes actual**. En ambos modos se omiten los eventos de todo el día.

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
# Ver todos los eventos del mes actual (salida por defecto: events-AAAA-MM.json)
uv run calendar-tool --range month

# Limitar a cuentas/calendarios concretos
uv run calendar-tool --account trabajo --calendar primary

# Elegir formato y ruta de salida
uv run calendar-tool --format csv --output hoy.csv

# Modo simple, sin config (una sola cuenta ad-hoc)
uv run calendar-tool --credentials creds.json --token tok.json

# Incluir las entradas de "Ubicación de trabajo" (Home/Office), excluidas por defecto
uv run calendar-tool --include-working-location
```

Los **eventos de todo el día** no se incluyen en la salida (en ninguno de los dos
modos). Las entradas de **Ubicación de trabajo** ("Home"/"Office",
`eventType: workingLocation`) son un caso aparte: aunque también son de todo el día,
se **excluyen por defecto** porque no son eventos a los que se asista, pero puedes
incluirlas con `--include-working-location`. Cada evento del archivo incluye su
`event_type` para que puedas distinguirlos.

El modo se refleja en el resumen por pantalla, que indica el modo («día actual» o
«mes actual») y la ventana exacta consultada. El archivo de salida por defecto es
`events-AAAA-MM-DD.{json,csv}` en modo día y `events-AAAA-MM.{json,csv}` en modo mes.

Si una cuenta falla (token caducado/revocado, restricción de la org, red), las
demás se entregan igualmente y el error se reporta por separado.

## Desarrollo

```bash
uv run ruff format . && uv run ruff check --fix .
uv run pytest
```
