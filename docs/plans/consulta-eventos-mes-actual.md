# Plan: Opción de consulta «mes actual» para los eventos del calendario
**Spec de Referencia**: `consulta-eventos-mes-actual` — añadir un modo «mes actual» (todos los eventos del mes, ventana `[día 1 00:00, fin de mes]`, sin filtro de "pendientes" y sin eventos de todo el día) manteniendo «día actual» como comportamiento por defecto.

## Contexto Técnico (Stack)
* **Lenguaje/Framework**: Python 3.12+, CLI con `argparse`, layout `src/` (`src/calendar_tool/`). Entorno y dependencias con **uv** (`pyproject.toml` + `uv.lock`). Lint/formato con **Ruff** (line-length 100). Ver `docs/TECH_STACK.md`.
* **Base de Datos**: No aplica. Única persistencia: tokens OAuth por cuenta (caché local) y el archivo de salida (JSON/CSV). El feature no añade persistencia.
* **Consideraciones**:
  * La lógica vive en funciones **puras y deterministas** en `events.py` (reciben `now` y `tz`), testeadas sin red con `FakeCalendarClient` y reloj fijo (`tests/conftest.py`, `tests/fakes.py`). El feature debe seguir ese patrón.
  * La API de Google (`events.list` con `timeMin/timeMax` + `singleEvents=True`) devuelve eventos por **solapamiento** con la ventana → el cruce de borde de mes sale resuelto sin lógica extra.
  * Las entradas de **«Ubicación de trabajo»** (Home/Office) son técnicamente all-day y ya tienen su propio flag (`--include-working-location`, excluidas por defecto); el nuevo filtro de all-day no debe romper ese comportamiento.
  * Acceso **solo lectura** intacto: el feature solo cambia la ventana y el filtrado en memoria, nunca los scopes ni las escrituras (no hay).

## Decisiones de Diseño Técnico
1. **Selección de modo por flag de CLI `--range {day,month}` (por defecto `day`)**: nuevo argumento en `cli.py` que mapea «día actual» → `day` y «mes actual» → `month`. *Por qué*: explícito y extensible (admite futuros `week`, etc.) sin alterar el comportamiento por defecto que exige la Historia 2. *Trade-off*: un flag más a documentar. (No se añade a `accounts.toml` en el MVP; un `range` por defecto en config queda como mejora posterior.)

2. **Ventana temporal por modo: se reutiliza `day_bounds(now)` y se añade `month_bounds(now)` en `events.py`**: `month_bounds` devuelve `[primer día del mes 00:00:00, primer día del mes siguiente 00:00:00)`, calculando el mes siguiente con `day=1` (con salto de año en diciembre→enero). *Por qué*: el límite superior **exclusivo** en el primer instante del mes siguiente es equivalente a "hasta el último día a las 23:59:59", es exactamente el `timeMax` que espera la API y evita calcular el "último día" (28/29/30/31 salen gratis al no construir fechas inválidas). *Trade-off*: la ventana es semiabierta, no un `23:59:59` literal (equivalente en la práctica y más robusto; DST lo absorbe `zoneinfo`).

3. **El cruce del borde del mes se resuelve con la propia API (sin trabajo extra)**: `list_raw_events(cal, timeMin, timeMax)` con `singleEvents=True` (ya existente en `calendar_client.py`) devuelve los eventos que **solapan** la ventana —los que empiezan antes del día 1 pero terminan dentro, y los que empiezan dentro y terminan el mes siguiente—. *Por qué*: cumple "se incluyen si solapan la ventana" sin lógica adicional; `combine_and_sort` (sin cambios) los ordena por inicio. *Trade-off*: un evento que arranca el mes anterior aparece ordenado al principio del listado (correcto, conviene saberlo). **Sin cambios en `calendar_client.py`.**

4. **Filtrado parametrizado por modo: `collect_pending_events` se generaliza a `collect_events(..., pending_only)`**: en modo día `pending_only=True` (mantiene el filtro `fin > ahora`, incluye los eventos en curso); en modo mes `pending_only=False` (incluye también los ya terminados dentro del mes). *Por qué*: una sola ruta de recolección con la única diferencia expresada como parámetro testeable, sin duplicar código. *Trade-off*: cambia la firma → hay que actualizar la llamada en `cli.py` y los tests existentes.

5. **Exclusión de eventos de todo el día en ambos modos, preservando «Ubicación de trabajo»**: dentro de `collect_events` se descartan los eventos `all_day`, y esa comprobación se evalúa **después** de la de `workingLocation`, de modo que Home/Office sigan gobernados por `--include-working-location` y su comportamiento no cambie. *Por qué*: cumple el Must-Have "NO DEBE incluir eventos de todo el día" sin romper la función de Ubicación de trabajo. *Trade-off*: **cambia el comportamiento actual del modo día** (un festivo o «Vacaciones» de hoy deja de aparecer); hay que actualizar los tests del modo día (asumido al elegir "ambos modos").

6. **Nombre de salida y resumen por modo; contenido del archivo sin cambios (Historia 3, P2, vía resumen)**: el archivo usa `events-{YYYY-MM-DD}.{fmt}` en día y `events-{YYYY-MM}.{fmt}` en mes (no se pisan); el resumen por `stderr` (`_print_summary`) indica el **modo** y la **ventana exacta [inicio, fin)**. El **contenido** del archivo (array JSON / filas CSV) se mantiene SIN cambios para no romper consumidores ni `test_output.py`. *Por qué*: satisface la intención de la Historia 3 (saber qué se consultó) en el MVP sin tocar el contrato de salida. *Trade-off*: incrustar metadatos (modo/rango) **dentro** del archivo queda como mejora posterior. **Sin cambios en `output.py`.**

## Estructura de Archivos Propuesta
<!--
Mapa para las tareas. Componente único: CLI de Python (src/ layout). Sin Android/iOS/KMP.
Cambio acotado: la ventana y el filtrado por modo viven en events.py (puro/testeable) y se cablean en cli.py.
-->

```
calendar-tool/
│
├── /src/calendar_tool
│   ├── events.py          <-- MODIFICADO (añadir month_bounds; collect_pending_events → collect_events con pending_only;
│   │                          excluir all-day en ambos modos, tras la regla de workingLocation)
│   └── cli.py             <-- MODIFICADO (flag --range {day,month} def. day; elegir day_bounds/month_bounds y pending_only;
│                              nombre de salida por modo; resumen con modo + ventana [inicio, fin))
│
├── /tests
│   ├── test_events.py     <-- MODIFICADO (month_bounds: longitudes de mes y dic→ene; collect_events modo mes incluye
│   │                          terminados; all-day excluidos en ambos modos; solapamiento de cruce de mes; nueva firma)
│   └── fakes.py           <-- (sin cambios; se reutilizan FakeCalendarClient, raw_event y all_day_event)
│
├── README.md              <-- MODIFICADO (documentar --range month, exclusión de all-day y nombre de salida del mes)
│
└── docs/
    ├── /specs/consulta-eventos-mes-actual.md   <-- (Spec, existente)
    ├── /plans/consulta-eventos-mes-actual.md   <-- NUEVO (este Plan)
    └── TECH_STACK.md                            <-- MODIFICADO (opcional: mencionar el modo «mes actual» en el resumen)
```

**Sin cambios** en: `models.py` (`CalendarEvent.all_day` ya existe), `calendar_client.py` (`list_raw_events` ya acepta cualquier ventana), `output.py` (formato intacto en el MVP), `config.py` (el modo se pasa por CLI). No hay otras plataformas: es un único componente CLI en Python.
