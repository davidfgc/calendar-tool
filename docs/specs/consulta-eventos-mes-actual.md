# Spec: Opción de consulta «mes actual» para los eventos del calendario
**Descripción General**: Ampliación de la herramienta de lectura de calendarios de Google para que, además de su comportamiento actual (mostrar los próximos eventos de **hoy** que aún no han terminado), ofrezca una opción de **«mes actual»**. En ese modo, la herramienta muestra **todos** los eventos del mes en curso, desde el **primer día del mes a las 00:00:00** hasta el **último día del mes a las 23:59:59**, sin filtrar los que ya hayan terminado. El comportamiento por defecto sigue siendo el de «día actual»; el modo «mes actual» es una opción que el usuario elige cuando quiere la foto completa del mes. Todas las garantías del spec vigente (solo lectura, multi-cuenta/calendario, vista combinada ordenada, volcado a archivo y aislamiento de fallos) se conservan en ambos modos.

## Historias de Usuario (El "Qué")
<!--
Describe los viajes del usuario.
Prioridad 1 (MVP) es lo mínimo indispensable.
-->

### Historia 1: Consultar todos los eventos del mes actual (Prioridad: 1 - MVP)
**Como** usuario con calendarios en Google, **Quiero** poder elegir la opción «mes actual» al ejecutar la herramienta, **Para** ver de un vistazo todos los eventos del mes completo y no solo los de hoy.
**Criterios de Aceptación (Cómo sabremos que funciona):**
**Dado** que selecciono la opción «mes actual», **Cuando** ejecuto la herramienta, **Entonces** obtiene todos los eventos comprendidos entre el primer día del mes a las 00:00:00 y el último día del mes a las 23:59:59, en una zona horaria consistente.
**Dado** que estoy en modo «mes actual», **Cuando** existen eventos del mes que ya terminaron antes del momento actual, **Entonces** esos eventos SÍ se incluyen (no se aplica el filtro de "aún no terminados" propio del modo día).
**Dado** que estoy en modo «mes actual», **Cuando** hay eventos de todo el día dentro del mes, **Entonces** esos eventos NO se incluyen en los resultados.
**Dado** que estoy en modo «mes actual», **Cuando** se vuelca el resultado, **Entonces** los eventos aparecen ordenados de forma ascendente por fecha y hora de inicio, con el mismo criterio de desempate estable que el modo día (p. ej. por hora de fin y luego por título).
**Dado** que estoy en modo «mes actual», **Cuando** se ejecuta, **Entonces** se mantiene el acceso exclusivamente de solo lectura, sin crear, modificar ni eliminar nada.

### Historia 2: Mantener «día actual» como comportamiento por defecto (Prioridad: 1 - MVP)
**Como** usuario que ya usa la herramienta, **Quiero** que, si no indico ninguna opción, siga mostrando los próximos eventos de hoy como hasta ahora, **Para** conservar el flujo actual sin cambios ni sorpresas.
**Criterios de Aceptación:**
**Dado** que ejecuto la herramienta sin indicar modo, **Cuando** se ejecuta, **Entonces** se comporta como el modo «día actual» del spec vigente (solo eventos de hoy cuya hora de fin es posterior al momento actual), **con la única diferencia** de que los eventos de todo el día dejan de mostrarse (ver Requisitos Clave).
**Dado** que quiero ese comportamiento de forma explícita, **Cuando** elijo la opción «día actual», **Entonces** obtengo el mismo resultado que el modo por defecto.
---

### Historia 3: Identificar en la salida el modo y el rango consultado (Prioridad: 2)
**Como** usuario que revisa el archivo de salida, **Quiero** saber qué modo se usó y qué rango exacto de fechas/horas se consultó, **Para** interpretar los resultados sin ambigüedad, sobre todo al comparar un archivo de día con uno de mes.
**Criterios de Aceptación:**
**Dado** que ejecuto en cualquiera de los dos modos, **Cuando** se genera el archivo, **Entonces** el resultado indica el modo («día actual» o «mes actual») y el rango de fechas/horas considerado.
---

## Casos Borde y Escenarios de Error
* ¿Qué pasa si **el mes no tiene ningún evento**? → Debe generar una salida válida pero vacía (lista vacía), no fallar.
* ¿Cómo se manejan los **eventos que cruzan el borde del mes** (empiezan en el mes anterior y terminan dentro, o empiezan dentro y se extienden al mes siguiente)? → Se incluyen si solapan en algún momento la ventana del mes.
* ¿Cómo se calcula el **último día del mes** en meses de distinta longitud (28/29/30/31) y en **febrero bisiesto**? → El fin de la ventana debe calcularse correctamente para cada mes.
* ¿Qué pasa con los **cambios de horario de verano (DST)** dentro del mes? → La ventana `[inicio, fin]` debe seguir siendo coherente en la zona horaria consistente.
* ¿Cómo se manejan los **eventos de todo el día** o **sin hora definida**? → NO se incluyen en los resultados; quedan excluidos en ambos modos.
* ¿Qué pasa con el **volumen alto de eventos** de un mes frente a un solo día? → La salida debe seguir siendo válida y manejable.
* ¿Qué pasa si **una cuenta o calendario falla** en modo mes? → Mismo aislamiento de fallos que en modo día: las cuentas correctas se entregan y las que fallan se reportan por separado.
* ¿Qué pasa si **se indica un modo no reconocido** o una opción inválida? → Debe quedar definido el comportamiento (p. ej. error claro o caer al modo por defecto), sin romper.
* ¿Qué pasa si **el archivo de salida ya existe**? → Mismo criterio que el spec vigente (sobrescritura o versionado), sin pérdida silenciosa de datos.

## Requisitos Clave (Must-Haves)
* El sistema DEBE ofrecer una opción para elegir el rango de consulta entre **«día actual» (por defecto)** y **«mes actual»**.
* El sistema DEBE, en modo «mes actual», devolver **todos los eventos comprendidos entre el primer día del mes a las 00:00:00 y el último día del mes a las 23:59:59** de la zona horaria consistente.
* El sistema DEBE, en modo «mes actual», **incluir también los eventos que ya hayan terminado** dentro del mes (no aplica el filtro de "aún no terminados" del modo día).
* El sistema DEBE **incluir los eventos que solapen la ventana del mes** aunque empiecen antes del primer día o terminen después del último día del mes.
* El usuario DEBE poder mantener **«día actual» como comportamiento por defecto** cuando no indique opción, sin cambios respecto al spec vigente.
* El sistema DEBE calcular correctamente el **último día del mes** (28/29/30/31, incluido febrero bisiesto).
* El sistema NO DEBE **incluir eventos de todo el día** (sin hora de inicio/fin definida) en los resultados.
* El sistema DEBE conservar en **ambos modos** el resto de garantías del spec vigente: solo lectura, multi-cuenta/multi-calendario, vista combinada ordenada por hora de inicio indicando el origen, volcado a archivo (JSON/CSV) y aislamiento de fallos por cuenta/calendario.
* El sistema NO DEBE **crear, modificar ni eliminar** ningún evento ni dato en ningún modo.

## Criterios de Éxito (El "Por Qué")
* Sabremos que esto es un éxito si, en una sola ejecución eligiendo «mes actual», el usuario obtiene **todos los eventos del mes ordenados por hora**, sin repetir la consulta día a día. *(propuesta a confirmar)*
* Sabremos que es un éxito si el **comportamiento por defecto sigue siendo idéntico al actual** (cero regresiones para quien ya usa la herramienta). *(propuesta a confirmar)*
* El objetivo es dar visibilidad tanto del **"qué me queda hoy"** como del **"cómo viene el mes"** con la misma herramienta y sin cambiar de contexto. *(propuesta a confirmar)*
