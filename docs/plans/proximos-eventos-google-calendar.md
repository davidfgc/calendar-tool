# Plan: Lector de próximos eventos de hoy de calendarios de Google
**Spec de Referencia**: `proximos-eventos-google-calendar` — script en solo lectura que obtiene los eventos de hoy aún pendientes de varias cuentas/calendarios de Google y los vuelca, combinados y ordenados por hora, a un archivo (JSON/CSV).

## Contexto Técnico (Stack)
* **Lenguaje/Framework**: Python 3.12+, herramienta de línea de comandos (CLI). Dependencias y entorno gestionados con **uv** (`pyproject.toml` + `uv.lock`). Ver `docs/TECH_STACK.md`.
* **Base de Datos**: No aplica. No hay BBDD; la única persistencia en disco son los **tokens OAuth por cuenta** (caché local, fuera de control de versiones) y el **archivo de salida** (JSON/CSV).
* **Consideraciones**:
  * Acceso a Google **exclusivamente de solo lectura** (scope `calendar.readonly`); jamás scopes de escritura.
  * **Las cuentas de trabajo y de cliente pueden tener restricciones** de organización (apps no verificadas, consentimiento de admin, bloqueo de OAuth de terceros). El diseño debe permitir credenciales distintas por cuenta y aislar fallos.
  * **Supuesto de diseño** (no se confirmó en preguntas): cada contexto se trata como una **cuenta autenticada por separado vía OAuth de usuario**. Si en la práctica un cliente te **comparte** su calendario hacia tu cuenta personal, ese caso queda cubierto sin trabajo extra: aparece como un calendario más de tu cuenta personal (multi-calendario).

## Decisiones de Diseño Técnico
1. **Autenticación OAuth de usuario (installed-app flow) con scope solo lectura**: Se usarán las librerías oficiales `google-api-python-client` + `google-auth-oauthlib`, con el flujo OAuth de aplicación de escritorio y el scope `https://www.googleapis.com/auth/calendar.readonly`. *Por qué*: es el camino soportado por Google para leer calendarios propios o compartidos; el scope readonly garantiza por contrato que la herramienta no puede modificar nada. *Trade-off*: la primera vez cada cuenta requiere un consentimiento interactivo en el navegador.

2. **Multi-cuenta declarado en config, con credenciales y token por cuenta**: Un archivo de configuración (`accounts.toml`) declara cuentas con nombre (`personal`, `trabajo`, `cliente-x`), cada una con su `credentials_file` (OAuth client secret) y su archivo de token cacheado en un directorio de tokens. *Por qué*: aísla las cuentas, permite que **trabajo/cliente usen su propio OAuth client** (clave para sortear restricciones de su organización) y habilita reautenticar o revocar una cuenta sin tocar las demás. *Trade-off*: más configuración inicial que una sola cuenta hardcodeada.

3. **Tolerancia a restricciones y aislamiento de fallos por cuenta**: La obtención de eventos se hace cuenta por cuenta de forma independiente; si una cuenta falla (token caducado/revocado, app bloqueada por la org, error de red), se registra ese fallo por separado y **se continúa con las demás**. El config admite, como vía opcional para orgs que lo provean, una `service_account` con *domain-wide delegation*; el modo por defecto es OAuth de usuario. *Por qué*: las restricciones varían por organización y no deben tumbar toda la ejecución. *Trade-off*: el reporte de salida debe distinguir "sin eventos" de "no se pudo leer".

4. **Filtrado "pendientes de hoy" y vista combinada**: Por cada calendario se llama a `events().list` con `timeMin`/`timeMax` acotados al **día actual** en la zona horaria configurada, `singleEvents=True` y `orderBy=startTime` (expande recurrencias). Después se filtran en memoria los eventos cuya **hora de fin sea posterior al instante actual** (así se incluyen los **en curso**) y se combinan todos ordenados por hora de inicio, con desempate estable por hora de fin y luego título. *Por qué*: pedir `timeMin=ahora` descartaría los eventos en curso; por eso se pide la ventana del día y se filtra por `fin > ahora`. *Trade-off*: hay que decidir el tratamiento de eventos de día completo (se incluyen y se ordenan al inicio del día).

5. **Modelo de dominio normalizado y salida JSON/CSV**: Un modelo `CalendarEvent` (inicio, fin, título, cuenta de origen, calendario, ubicación/enlace, asistentes) desacopla la respuesta de la API de los escritores. Un módulo `output` serializa la lista combinada a **JSON** (estructura anidada) o **CSV** (plano), seleccionable por flag de CLI. *Por qué*: separar dominio de presentación permite añadir formatos sin tocar la lógica. *Trade-off*: el CSV exige aplanar campos como asistentes (p. ej. unidos por `;`).

6. **CLI con `src/` layout y tests con fakes (sin red)**: Punto de entrada en `pyproject.toml` (`[project.scripts]`), parseo de argumentos en `cli.py`. Los tests usan un `FakeCalendarClient` y un **reloj fijo** para validar el filtro `fin > ahora`, el orden combinado y las zonas horarias sin llamar a Google. *Por qué*: la lógica de negocio (filtro/orden/zonas/salida) debe ser testeable de forma determinista y aislada de la API y de las credenciales. *Trade-off*: requiere una frontera limpia entre el wrapper de la API y la lógica.

## Estructura de Archivos Propuesta
<!--
Mapa para las tareas. Componente único: un CLI de Python (src/ layout).
No hay otras plataformas (sin Android/iOS/KMP). MVP = una cuenta/calendario → archivo;
multi-cuenta y vista combinada quedan habilitadas por la misma estructura (Prioridad 2 del Spec).
-->

calendar-tool/
│
├── pyproject.toml                 <-- NUEVO (proyecto, deps vía uv, script de CLI, Ruff)
├── uv.lock                        <-- NUEVO (lockfile, generado por uv)
├── .gitignore                     <-- NUEVO (excluye tokens/, *credentials*.json, salidas)
├── accounts.example.toml          <-- NUEVO (plantilla de config multi-cuenta, SIN secretos)
├── README.md                      <-- NUEVO (setup OAuth y uso)
│
├── docs/
│   ├── TECH_STACK.md              <-- (existente)
│   ├── /specs
│   │   └── proximos-eventos-google-calendar.md   <-- (Spec)
│   └── /plans
│       └── proximos-eventos-google-calendar.md   <-- (este Plan)
│
├── /src/calendar_tool
│   ├── __init__.py                <-- NUEVO
│   ├── __main__.py                <-- NUEVO (permite `python -m calendar_tool`)
│   ├── cli.py                     <-- NUEVO (args, orquesta auth->fetch->filtro->salida)
│   ├── config.py                  <-- NUEVO (carga accounts.toml, rutas de tokens/credenciales)
│   ├── auth.py                    <-- NUEVO (OAuth installed-app, scope readonly, caché de token por cuenta)
│   ├── calendar_client.py         <-- NUEVO (wrapper Calendar API: listar calendarios y eventos)
│   ├── events.py                  <-- NUEVO (filtro "fin > ahora", combinación y orden por hora)
│   ├── models.py                  <-- NUEVO (dataclasses: Account, CalendarRef, CalendarEvent)
│   └── output.py                  <-- NUEVO (escritores JSON / CSV)
│
└── /tests
    ├── conftest.py                <-- NUEVO (fixtures: reloj fijo, config de prueba)
    ├── fakes.py                   <-- NUEVO (FakeCalendarClient, sin red)
    ├── test_events.py             <-- NUEVO (filtro pendientes, orden, zonas horarias, en curso)
    ├── test_output.py             <-- NUEVO (serialización JSON/CSV, aplanado de asistentes)
    └── test_config.py             <-- NUEVO (carga y validación de cuentas)

Sin cambios en otras plataformas: es un único componente CLI en Python (no hay Android, iOS ni KMP en este proyecto).
