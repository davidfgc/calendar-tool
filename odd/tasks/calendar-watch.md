# calendar-watch: consolidación, alarmas y conflictos

Servicio en segundo plano que consolida los calendarios de `calendar-tool` en SQLite
(`calendar-tool sync`) y avisa de reuniones y conflictos (`calendar-watch`) en macOS y
Android (ntfy). El dashboard (`pulse`) queda fuera de alcance.

## Specs

- **S1 — Consolidar.** "primero me consolide las reuniones". `calendar-tool sync` lee todas
  las cuentas de la config sin interacción (nunca abre el navegador) y guarda en SQLite los
  eventos de las próximas 48 h (configurable). La misma reunión presente en varias cuentas se
  trata como una sola (por `iCalUID`). Si una cuenta falla, las demás se guardan y su error
  queda registrado.
- **S2 — Conflictos.** "me alerte en caso de conflicto". Dos reuniones que se solapan generan
  un aviso, una sola vez por conflicto. No cuentan: reuniones rechazadas, marcadas como
  "disponible", de todo el día, ni Ubicación de trabajo / Fuera de la oficina.
- **S3 — Alarmas.** "me sirva como alarma 1m antes para conectarme"; momentos elegidos:
  "10 y 1 minuto antes". El aviso incluye el enlace de la reunión (Meet/Zoom/Teams) cuando
  existe. No se avisa de reuniones rechazadas.
- **S4 — macOS.** "Ambas por fases": fase 1 = notificación + sonido; la pantalla completa es
  fase 2 (fuera de esta entrega).
- **S5 — Android.** "ntfy.sh, canal secreto, con título". El canal vive en la config
  (ignorada por git), nunca en el repositorio.
- **S6 — Nombre.** "Comando aparte: calendar-watch (Recomendado)": mismo paquete, otro comando.
- **S7 — Cuenta sin actualizar.** Si una cuenta lleva más de 15 min sin sincronizar con éxito,
  avisar "cuenta X sin actualizar, vuelve a iniciar sesión" (una vez por episodio).
- **S8 — Compatibilidad.** `calendar-tool` (sin subcomando) se comporta igual que antes. Acceso
  a Google exclusivamente de solo lectura (TECH_STACK: no negociable).
- **S9 — Arranque automático.** `sync` cada 2 min y `watch` siempre encendido vía `launchd`.
  Se generan los plists; instalarlos es decisión del usuario.

## Tasks

| ID | Specs | Qué | Ruta | Commit |
|---|---|---|---|---|
| T1 | S1, S3, S8 | Rango configurable, campos nuevos (iCalUID, respuesta, transparencia, enlace, updated), extracción reutilizable | inline | 72f7f81 |
| T2 | S1, S8 | Store SQLite + `calendar-tool sync` + deduplicación | inline | b5e6cff |
| T3 | S2, S3, S4, S6, S7, S9 | `calendar-watch`: planificador, conflictos, cuentas sin actualizar, notificación macOS, plists | worker | 44b9c19 |
| T4 | S5 | Notificador ntfy (JSON, canal secreto en config) | inline | accfdd2 |

## Log

- **L1** (petición original): "el problema es el siguiente, tengo 4 calendarios diferentes
  entre el personal, dos trabajos y un cliente y se me suelen pasar algunas reuniones, además
  que a veces puedo saber que la tengo en 15m, 10m o menos, pero me ditraigo con algo y se me
  olvida / quiero contruir una solución que primero me consolide las reuniones, que pueda ver
  fácilmente dentro cuánto es la próxima, me alerte en caso de conflicto, y me sirva como
  alarma 1m antes para conectarme"
- **L2**: "pulse va a ser la web/dashboard de consulta, que por ahora no vamos a implementar /
  entonces dentro de calendar-tools, podemos agregar el servicio en background que estamos
  hablando, seguramtente con un nombre diferente"
- **L3** (decisiones): nombre "Comando aparte: calendar-watch (Recomendado)"; alarma macOS
  "Ambas por fases"; Android "ntfy.sh, canal secreto, con título"; momentos "10 y 1 minuto
  antes"; alcance "Sí, empieza por las unidades 1–4".
- **L4** (decisión técnica): no se cambian los valores por defecto de rutas de `calendar-tool`
  (sería un cambio de contrato); `sync`/`watch` reciben `--config` absoluta desde los plists y
  la base de datos vive por defecto en `~/.local/share/calendar-tool/calendar.db`. La zona
  horaria se resuelve en cada ciclo para no desfasarse con el horario de verano.
- **L5** (verificación): 96 tests en verde; `sync` real (personal, zoox OK; work `invalid_grant`;
  baires sin autorizar); `calendar-watch --once` real envió 2 avisos de cuenta sin actualizar y
  1 conflicto real, y el segundo ciclo no repitió; plists válidos (`plutil -lint`).
- **L6** (revisión nativa, lineage review-f0b59139793fb9dd, b5e6cff..accfdd2, lentes risk,
  resilience, reliability): aprobada. 12 hallazgos no bloqueantes pendientes como trabajo
  aparte, los más relevantes: marcar como enviado aunque fallen todos los canales (se pierde la
  alarma de 1 min), recordatorios enviados después de los conflictos, fallos de ciclo
  silenciosos (`timezone` sin validar, `--once` devuelve 0), `--log-dir` relativo en plists,
  enlace sin validar `https`, servidor ntfy `http://` aceptado.
