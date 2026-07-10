# Tasks: Opción de consulta «mes actual» para los eventos del calendario

## Fase 1: Setup / Fundacional
<!-- Cambios compartidos por los dos modos (día y mes): bloquean a las Historias MVP. -->
* [ ] **[Setup]** Modificar `src/calendar_tool/events.py`: generalizar `collect_pending_events` → `collect_events` añadiendo el parámetro `pending_only` (sin cambiar aún el filtrado/mapeo), para que ambos modos compartan la recolección. *(Plan, Decisión 4)*
* [ ] **[Setup]** Modificar `src/calendar_tool/events.py`: excluir los eventos `all_day` dentro de `collect_events`, evaluándolo **después** de la regla `workingLocation` para no romper `--include-working-location`. *(Plan, Decisión 5)*
* [ ] **[Setup]** Modificar `src/calendar_tool/cli.py`: añadir en `build_parser()` el flag `--range {day,month}` con valor por defecto `day`. *(Plan, Decisión 1)*
---

## Fase 2: Historia 1 - Consultar todos los eventos del mes actual (MVP)
* [ ] **[Historia 1 - Lógica]** Añadir `month_bounds(now)` en `src/calendar_tool/events.py`: ventana `[día 1 00:00, día 1 del mes siguiente 00:00)`, con salto de año diciembre→enero. *(Plan, Decisión 2)*
* [ ] **[Historia 1 - Wiring]** Modificar `run()` en `src/calendar_tool/cli.py`: según `--range`, elegir `day_bounds`/`month_bounds` y el `pending_only` (día=`True`, mes=`False`) y pasarlo a `collect_events`. *(Plan, Decisiones 1, 3, 4)*
* [ ] **[Historia 1 - Wiring]** Modificar `run()` en `src/calendar_tool/cli.py`: nombre de archivo de salida por modo (`events-{YYYY-MM}.{fmt}` en mes; se conserva `events-{YYYY-MM-DD}.{fmt}` en día). *(Plan, Decisión 6)*
* [ ] **[Historia 1 - Test]** Añadir en `tests/test_events.py` tests de `month_bounds`: longitudes de mes (28/29/30/31) y salto diciembre→enero.
* [ ] **[Historia 1 - Test]** Añadir en `tests/test_events.py` test de `collect_events` en modo mes (`pending_only=False`): incluye eventos del mes que **ya terminaron**.
* [ ] **[Historia 1 - Test]** Añadir en `tests/test_events.py` test de **cruce de borde de mes**: un evento que solapa la ventana aparece (apoyado en el solapamiento de `timeMin/timeMax`).
* [ ] **[Historia 1 - Test]** Añadir en `tests/test_events.py` test de que el modo mes **excluye** los eventos de todo el día.
* [ ] **[Historia 1 - Docs]** Modificar `README.md`: documentar `--range month`, el nombre de salida `events-{YYYY-MM}` y que ya no se muestran eventos de todo el día.
---

## Fase 3: Historia 2 - Mantener «día actual» como comportamiento por defecto (MVP)
<!-- Sin código nuevo de producción aquí: el flag por defecto (Fase 1) y el cableado de run() (Historia 1)
ya realizan el modo día. El trabajo de esta Historia es preservar el comportamiento y testearlo (incl. el cambio de all-day). -->
* [ ] **[Historia 2 - Test]** Modificar `tests/test_events.py`: adaptar los tests de día existentes (`test_collect_pending_filtra_y_mapea`, `test_working_location_excluida_por_defecto`) a la nueva firma `collect_events(..., pending_only=True)`.
* [ ] **[Historia 2 - Test]** Añadir en `tests/test_events.py` test de que el modo día (por defecto) ya **NO** incluye los eventos de todo el día "normales", verificando que `--include-working-location` **sigue** mostrando Home/Office.
---

## Fase 4: Historia 3 - Identificar en la salida el modo y el rango consultado (Prioridad 2)
* [ ] **[Historia 3]** Modificar `_print_summary()` (y su llamada en `run()`) en `src/calendar_tool/cli.py`: mostrar el **modo** («día actual»/«mes actual»), la **ventana `[inicio, fin)`** consultada y un conteo etiquetado según el modo. *(Plan, Decisión 6)*
---

## Fase 5: Verificación y cierre
* [ ] **[Verificación]** Formato y lint: `uv run ruff format .` && `uv run ruff check --fix .`
* [ ] **[Verificación]** Tests: `uv run pytest`
* [ ] **[Docs]** *(opcional)* Modificar `docs/TECH_STACK.md`: mencionar el modo «mes actual» en el resumen del proyecto.

---

**Trazabilidad / Sin cambios** (del Plan): no se tocan `models.py` (`CalendarEvent.all_day` ya existe), `calendar_client.py` (`list_raw_events` ya acepta cualquier ventana), `output.py` (formato de archivo intacto en el MVP), `config.py` (el modo va por CLI) ni `tests/fakes.py` (se reutilizan `FakeCalendarClient`, `raw_event`, `all_day_event`).
