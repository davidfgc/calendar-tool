# Spec: Lector de próximos eventos de hoy de calendarios de Google
**Descripción General**: Herramienta (script) que se conecta en modo **solo lectura** a uno o varios calendarios de Google —repartidos en distintas cuentas (personal, trabajo, cliente) y/o en distintos calendarios dentro de cada cuenta— para obtener los eventos del día actual que aún no han terminado, y los vuelca a un archivo (JSON/CSV) en una vista combinada y ordenada por hora de inicio. El objetivo es tener, de un vistazo, "qué me queda hoy" sin riesgo de modificar nada en los calendarios.

## Historias de Usuario (El "Qué")
<!--
Describe los viajes del usuario.
Prioridad 1 (MVP) es lo mínimo indispensable.
-->

### Historia 1: Ver los próximos eventos de hoy de un calendario (Prioridad: 1 - MVP)
**Como** usuario con calendarios en Google, **Quiero** conectarme en solo lectura a un calendario y obtener los eventos de hoy que aún no han terminado, **Para** saber qué me queda por delante en el día sin riesgo de tocar nada.
**Criterios de Aceptación (Cómo sabremos que funciona):**
**Dado** que tengo acceso de lectura a un calendario, **Cuando** ejecuto la herramienta, **Entonces** se autentica en modo solo lectura y obtiene los eventos del día actual cuya hora de fin es posterior al momento actual.
**Dado** que la herramienta ha obtenido los eventos, **Cuando** termina, **Entonces** los vuelca a un archivo (JSON o CSV) con, como mínimo, hora de inicio, hora de fin y título de cada evento.
**Dado** que un evento ya terminó antes de la hora actual, **Cuando** se generan los resultados, **Entonces** ese evento NO aparece.
**Dado** que la herramienta solo tiene permisos de lectura, **Cuando** se ejecuta, **Entonces** en ningún caso crea, modifica ni elimina eventos.

### Historia 2: Conectar varias cuentas y calendarios (personal, trabajo, cliente) (Prioridad: 2)
**Como** usuario con varios contextos, **Quiero** registrar y leer eventos desde distintas cuentas de Google (personal, trabajo, cliente) y desde varios calendarios dentro de cada una, **Para** no depender de una sola cuenta ni cambiar de sesión manualmente.
**Criterios de Aceptación:**
**Dado** que he autorizado más de una cuenta de Google, **Cuando** ejecuto la herramienta, **Entonces** puede acceder a los eventos de cualquiera de ellas sin tener que reautenticar cada vez.
**Dado** que una cuenta tiene varios calendarios, **Cuando** consulto esa cuenta, **Entonces** puedo elegir leer uno, varios o todos sus calendarios.
**Dado** que cada evento puede venir de una cuenta/calendario distinto, **Cuando** se vuelca el resultado, **Entonces** cada evento indica de qué cuenta y calendario procede.

### Historia 3: Vista combinada y ordenada de todos los calendarios (Prioridad: 2)
**Como** usuario con la agenda repartida, **Quiero** ver en una sola ejecución los próximos eventos de hoy de todos los calendarios/cuentas juntos y ordenados por hora, **Para** entender mi día completo de un vistazo sin unir listas a mano.
**Criterios de Aceptación:**
**Dado** que tengo eventos en varias cuentas/calendarios, **Cuando** ejecuto la herramienta en modo combinado, **Entonces** el archivo de salida contiene todos los eventos juntos ordenados de forma ascendente por hora de inicio.
**Dado** que dos eventos coinciden en la misma hora de inicio, **Cuando** se ordenan, **Entonces** se aplica un criterio de desempate estable y predecible (p. ej. por hora de fin y luego por título).
---

## Casos Borde y Escenarios de Error
* ¿Qué pasa si **no hay ningún evento pendiente hoy** (agenda vacía o todos ya terminaron)? → Debe generar una salida válida pero vacía (lista vacía), no fallar.
* ¿Qué pasa si **la autorización ha caducado o fue revocada** para una cuenta? → Debe indicar claramente qué cuenta necesita reautenticarse, sin abortar las cuentas que sí funcionan.
* ¿Qué pasa si **una cuenta funciona pero otra falla** (error de red, sin permiso de lectura a un calendario)? → Debe devolver los eventos de las cuentas correctas y reportar por separado las que fallaron.
* ¿Cómo se manejan **las zonas horarias** (eventos en otra zona horaria que la del usuario, o cuentas con zonas distintas)? → El criterio de "hoy" y "ya pasó" debe ser coherente y mostrarse en una zona horaria clara y consistente.
* ¿Cómo se manejan los **eventos de todo el día** o **sin hora definida**? → Debe quedar definido si se incluyen y cómo se ordenan respecto a los eventos con hora.
* ¿Qué pasa con **eventos que ya empezaron pero aún no terminan** (en curso)? → Cuentan como "pendientes" y deben aparecer.
* ¿Qué pasa si **el usuario solo tiene permiso de lectura parcial** (calendario compartido de un cliente)? → Debe funcionar igualmente y, si hay campos no visibles, no romper.
* ¿Qué pasa si **el archivo de salida ya existe**? → Debe quedar definido si se sobrescribe o se versiona, sin pérdida silenciosa de datos.

## Requisitos Clave (Must-Haves)
* El sistema DEBE conectarse a Google Calendar **exclusivamente en modo solo lectura** y NO solicitar ni usar permisos de escritura.
* El sistema DEBE devolver **solo los eventos del día actual cuya hora de fin sea posterior al momento de la ejecución** (incluye los que están en curso).
* El sistema DEBE soportar **varias cuentas de Google distintas** y **varios calendarios dentro de cada cuenta**.
* El sistema DEBE poder presentar los eventos en una **vista combinada ordenada por hora de inicio**, indicando el origen (cuenta/calendario) de cada evento.
* El usuario DEBE poder obtener el resultado **volcado a un archivo (JSON o CSV)**.
* El sistema DEBE **aislar los fallos por cuenta/calendario**: si uno falla, los demás deben entregarse igualmente.
* El sistema NO DEBE **crear, modificar ni eliminar** ningún evento ni dato en los calendarios.
* El sistema NO DEBE **exponer ni almacenar credenciales de forma insegura**.

## Criterios de Éxito (El "Por Qué")
* Sabremos que esto es un éxito si, con una sola ejecución, el usuario obtiene en el archivo **todos sus próximos eventos de hoy de todas sus cuentas/calendarios, ordenados por hora**, sin tener que abrir cada calendario por separado. *(propuesta a confirmar)*
* Sabremos que es un éxito si la herramienta **nunca produce un cambio** en ningún calendario (verificable porque solo pide permisos de lectura). *(propuesta a confirmar)*
* El objetivo es **reducir el tiempo y el cambio de contexto** necesarios para saber "qué me queda hoy" entre vida personal, trabajo y clientes. *(propuesta a confirmar)*
