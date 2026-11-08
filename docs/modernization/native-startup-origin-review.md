# Arranque: conservar el origen antes de sustituir el error

El broker conserva ahora el diagnóstico original cuando una retirada durante el
arranque sustituye la excepción que recibe el coordinador. La prueba con un dominio
kernel real demostró el hueco: un `OSError` previo al gate terminaba como
`AuthorityConflict` con su contexto suprimido, sin registro del productor. El nuevo
registro pasa esa prueba sin cambiar la excepción externa ni las decisiones de
autoridad. **La causa del AuthorityBusy original sigue abierta.**

Bloque iniciado a las 02:28:30 UTC, base `b5b2b3c`; verificado a las 03:01:09 UTC:
**32 min 39 s hasta verificar**, sin documentación/checkpoint posteriores.

El nuevo evento del operador conserva clase de peer, etapa y hasta cuatro
ubicaciones internas por causa, con un máximo de cuatro causas. No contiene
mensajes de excepción, rutas de archivos, líneas de código ni variables locales.
Se emite después de retirar y cerrar físicamente el dominio. Un sumidero de log
que falla tampoco sustituye el error ni impide ese cierre. Las etapas distinguen
perfil, creación del proceso, observación de namespace, publicación, vínculo local
y entrega del gate; son diagnóstico, no autorización para repetir una operación.

La extracción se comparte con el coordinador mediante un módulo independiente,
conservando `service._failure_sites` como alias compatible. Los límites, CAS,
reservas, excepciones externas y protocolo del gate conservan su comportamiento.
El primer test falló antes del cambio y pasó después; otro comprueba el sumidero
roto. **88 casos de origen y 88 del paquete instalado pasan**, sin omisiones.
Son las mismas selecciones en dos entornos, no 176 escenarios distintos. Nueve
definiciones nuevas/modificadas tienen docstrings en inglés. La rueda limpia
coincide con 677 fuentes; todos los imports backend de validación vienen del
entorno instalado. `uv pip check` pasa. No hubo modelos reales.

Antes del cambio se hizo un único diagnóstico adicional desde Chromium. La web
envió una admisión y empezó 35 lecturas; alcanzó la guardia de generación con
cero turnos, peers y grants cerrados y fuente intacta. El `failed` final fue
deliberado. Existe una reserva SQL, de modo que la interfaz conserva prudentemente
el inicio de inferencia desconocido; las dos guardias del ensayo y el contador
nativo permiten afirmar cero envíos en ese ensayo. Los tiempos de inicio de las
lecturas no miden solapamiento de solicitudes dentro del servidor.

No apareció AuthorityBusy/Conflict en ese diagnóstico. Son seis observaciones sin
generación; no prueban fiabilidad intermitente. La revisión del código confirmó
que las guardias anteriores sí estaban después de abrir la sesión Codex y enlazar
su thread. Los logs originales confirman además que el plan inglés y el fallo
español usaron procesos API distintos, con fuentes de bytes idénticos: no se
presupone reutilización del mismo proceso. La historia retenida sigue siendo una
diferencia por investigar, sin atribuirle la causa ni modificar esos intentos.

DD129 conserva cuatro hallazgos de estilo de los archivos modificados: imports,
contextos anidados del test y dos avisos sobre la captura intencionada de errores
del sumidero. Ruff no se declara verde. Se atenderán después de las capacidades
mayores, conservando la prueba de que el log no controla la parada.

Siguen **3/12 páginas** y **41/43 escenarios** aceptados con sus alcances. El plan
español, auditoría real de consultas Ken, U08/C10 y cierre global permanecen
pendientes. El siguiente paso de esta investigación requiere un productor concreto
o una diferencia causal comprobable; no se encadenan más arranques equivalentes.

[Resultados](native-startup-origin-results.json), [paquete](native-startup-origin-packaging.json),
[docstrings](native-startup-origin-docstrings.json), [ensayo del navegador](native-preparation-browser-results.json),
[plan vigente](../superpowers/plans/2026-11-08-native-preparation-contention.md).

## Historia retenida y reinicio,2026-11-08

29c061d,10:45:40–10:51:41UTC,6min1s hasta verificar. Una revisión limpia independiente
trazó las lecturas ordinarias de Proyectos al store de negocio; no abren otro
journal. La configuración usa un handle transitorio antes de servir y cada
preparación comparte otro entre sus workers. No se encontró anidamiento durante
preparación. AuthorityBusy también puede provenir de capacidad de endpoints,
cola de lanzamiento o cierre de peer con gate ocupado: su clase no prueba flock.

Dos admisiones guardadas en un host sintético, separadas por cierre143y reinicio,
llegan a las dos guardias de generación.0turnos,0peers/grants abiertos,
integridadok; ambas concesiones retiradas con dominio eliminado. Historia18→36
transiciones,110571→220818bytes.45operaciones instrumentadas por sesión sobre
configuración/preparación; se registran handle/PID/thread e intervalos sin mensajes
privados. Ninguna excepción de autoridad. **No corrige el fallo original.**
La historia es de preparación/cierre, no de un plan aceptado. No se continúan
variantes equivalentes. Proyectos y fiabilidad original siguen principales;
siguiente macroindependiente: idempotencia de comentarios de tarea.
[Recibo](native-history-results.json), runner evals/operation/preparation_history.py.


## Revisión independiente del gate de Proyectos

Una revisión estática de contexto limpio sobre `d278653` no encontró evidencia
suficiente para afirmar una carrera interna. El requisito de modificar la
autoridad solo después de demostrar una causa se conserva. Se revisó la
dependencia que obligaba a producir esa corrección antes de aceptar cualquier
alcance de Proyectos: el contrato original permite aceptación acotada manteniendo
problemas mayores abiertos. El [plan correctivo](../superpowers/plans/2026-11-08-native-preparation-contention.md)
explicita el cambio y la comprobación pendiente sobre el intento original.

`service.py` distingue cierre confirmado e inferencia; Proyectos conserva el enlace
al run fallido y Tareas muestra su explicación. Falta acreditar ese recorrido
instalado tras recarga, conservando presupuesto y sin nueva admisión, además de
vincular Stop con su prueba anterior. La página y el incidente permanecen abiertos.
No se ejecutaron otra preparación ni otro turno como parte de esta revisión.
