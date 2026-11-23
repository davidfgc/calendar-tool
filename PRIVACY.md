# Política de privacidad — calendar-tool

Última actualización: 22 de noviembre de 2026

`calendar-tool` es una herramienta de línea de comandos de código abierto que se
ejecuta **en el equipo de quien la usa**. No hay servidores, cuentas ni servicios
operados por el autor: el autor no recibe, almacena ni ve ningún dato tuyo.

## Datos a los que accede

- Con tu consentimiento explícito (OAuth de Google), lee tus calendarios de Google
  con el scope de **solo lectura** `https://www.googleapis.com/auth/calendar.readonly`.
- Lee los eventos de un intervalo corto (hoy o las próximas horas): título, horario,
  estado de asistencia, tipo de evento y enlaces de videollamada.
- **Nunca** crea, modifica ni elimina eventos.

## Dónde se guardan

Todo queda en tu equipo, en las rutas que tú configuras:

- Tokens de OAuth (`token_file`) y credenciales (`credentials_file`).
- Archivos de salida JSON/CSV y la base SQLite de `calendar-tool sync`
  (por defecto `~/.local/share/calendar-tool/calendar.db`).
- Logs en `~/Library/Logs/calendar-tool/` si usas launchd.

## Con quién se comparten

Con nadie por defecto. La única excepción es opcional y la activas tú: si configuras
avisos por **ntfy** (`[notify.ntfy]`), la herramienta envía al servidor ntfy que
elijas (por defecto `ntfy.sh`) el título y el enlace de las reuniones próximas. Ese
servicio tiene su propia política de privacidad.

Los datos no se venden, no se usan para publicidad y no se usan para entrenar modelos
de IA.

## Uso limitado de datos de Google

El uso y la transferencia de información recibida de las APIs de Google se ajustan a
la [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
incluidos los requisitos de uso limitado (*Limited Use*).

## Cómo borrar tus datos o revocar el acceso

- Borra los archivos `token_file`, los JSON/CSV de salida y la base SQLite.
- Revoca el acceso de la app en <https://myaccount.google.com/permissions>.

## Contacto

Dudas o solicitudes: abre un issue en
<https://github.com/davidfgc/calendar-tool/issues>.
