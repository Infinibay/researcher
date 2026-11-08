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
