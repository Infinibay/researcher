# Preparación nativa: contención y explicación de fallos

## Revisión de la dependencia de aceptación — 2026-11-08

Una revisión independiente de solo lectura sobre `d278653` distingue el incidente
de disponibilidad de la aceptación técnica de Proyectos. El `AuthorityBusy`
original ocurrió, pero no demuestra una carrera interna: la misma clase cubre
contención, capacidad, cola y retirada. Exigir una causa demostrada antes de
modificar la autoridad sigue siendo correcto. Exigir producir una corrección
causal antes de aceptar cualquier alcance de la página era una dependencia
introducida por este plan, sin evidencia suficiente de ese defecto.

Para la aceptación de la página se sustituye esa dependencia de los pasos 5–6 por
el contrato original de recuperación, conservando las ejecuciones y criterios
anteriores como evidencia histórica:

1. Abrir en la instalación actual el intento fallido original desde Proyectos y
   volver a él después de recargar, conservando tarea, run y proyecto exactos.
2. Comprobar que la explicación visible, estado de cierre, inferencia y presupuesto
   concuerdan con el registro; no admitir trabajo ni repetir la preparación.
3. Vincular la evidencia existente de Stop con su requisito original, distinguiendo
   comprobación visual de verificación física del cierre.
4. Solo con esa evidencia, considerar una aceptación técnica/visual por alcance.
   El incidente desconocido y la aceptación humana U08 siguen separados.

La evidencia española/Ken posterior ya demuestra un recorrido funcional distinto;
no demuestra una corrección del incidente. **La página todavía no se declara
aceptada.** No se autoriza ignorar locks, liberar reservas por suposición ni
repetir preparaciones equivalentes. [Contrato original de páginas](2026-11-07-full-pages-acceptance.md),
[diagnóstico e incertidumbre](../../modernization/native-startup-origin-review.md),
[recorrido español](../../modernization/spanish-plan-ken-review.md).

## Plan y diagnóstico anteriores, conservados

La investigación correctiva empezó el2026-11-08 a las00:49:17 UTC. La explicación
del cierre se corrigió y se añadieron ubicaciones seguras al log. La contención
original todavía no se reprodujo ni se corrigió. Conservar las ejecuciones originales.

## Evidencia conocida

- Instalación retenida: `.researcher/evaluations/projects-acceptance-label-20261107`.
  Todos sus servidores y peers están cerrados; no hay un proceso por el que esperar.
- Proyecto 2: intento cancelado, log AuthorityConflict, ninguna inferencia; reserva
  de preparación conservada. Otra solicitud fue rechazada por presupuesto.
- Proyecto 3: plan real aceptado,139193 tokens observados, despacho settled.
- Proyecto 5: solicitud española persistida, fallo AuthorityBusy antes de inferir;
  peers cerrados. No hubo respuesta española ni reintento.
- Log del producto: `host/logs/infinibay.log`, no sólo stdout del servidor.
  No copiar códigos de acceso ni el fichero privado de recursos.
- `authority_journal.py::_operation` tiene RLock por instancia, flock no bloqueante
  y traducción de SQLITE_BUSY/LOCKED. Falta localizar qué operación contendió.

## Trabajo

1. Revalidar recibos, logs y cierre original. Recuperar el llamador con diagnóstico
   acotado del operador; no exponer stack/credenciales en la interfaz. Distinguir
   hipótesis de concurrencia interna de un lock externo realmente poseído.
2. Reproducir la frontera sin inferencia de pago, usando procesos/journal reales
   cuando haga falta. Inspeccionar propietarios, callers, pruebas y blast radius
   antes de cambiar la transacción compartida.
3. Corregir sólo la causa demostrada. No ignorar locks, secuencias o hashes;
   no repetir escrituras inciertas ni liberar reservas por suposición. Una espera
   o conciliación tiene que estar acotada y preservar el efecto original.
4. Corregir la explicación de fallo para distinguir preparación fallida, inferencia
   no iniciada y cierre desconocido, usando pruebas de los estados reales.
5. Validar el cambio instalado. Sólo después, registrar una comprobación nueva de
   idioma sobre el producto corregido, conservando la propuesta inglesa y el
   intento español fallido. El proyecto 5 no tiene presupuesto libre para repetir
   su preparación: no reescribir ni borrar esa historia.
6. Volver a la aceptación de Proyectos y luego al resto de páginas. DD123/124 son
   detalles separados; esta fiabilidad del engine es trabajo principal.

## Corte diagnóstico

Cuatro preparaciones con generación prohibida llegaron a la guardia y cerraron
sus peers: tres con asyncio y la rueda previa; una con uvloop y la rueda nueva.
Cero turnos enviados. No bastan para cerrar la contención ni aceptar Proyectos.
La explicación ahora distingue cierre comprobado e inferencia incierta; los logs
permiten localizar el llamador sin registrar mensajes privados de excepción.
[Revisión y límites](../../modernization/native-preparation-review.md).

Antes de construir otro artefacto, consultar la regla de sdist + wheel limpio en
`docs/architecture/native-python-installation.md`. Un build directo arrastró306
módulos retirados y fue rechazado antes de ejecutar pruebas. Se sustituyó por
una rueda limpia verificada; no reutilizar el artefacto descartado.


La preparación HTTP bajo guardián/uvloop tampoco reprodujo el fallo; conservó
fuente, límites y reserva,0turnos y cierre comprobado. No se repiten casos iguales
indefinidamente. La fiabilidad queda como pendiente principal mientras se verifica
una capacidad independiente sin inferencia (Documentos), sin afirmar su corrección.


## Retoma con navegador real — 2026-11-08 02:28:30 UTC

Base `b5b2b3c`; 3/12 páginas y 41/43 escenarios comprobados. La preparación Git
real no reprodujo la contención nativa ni demuestra su corrección.

Ruling: un único ensayo adicional con navegador y sus peticiones naturales durante
la admisión. El HTTP anterior consultaba sus tres endpoints secuencialmente;
la concurrencia no era la de la página. Mantener ambas guardias que prohíben
generación, registrar el productor de AuthorityBusy/Conflict si aparece y conservar
el intento nuevo. No alterar locks/CAS, reservas, límites o instalaciones previas.

La guardia previa sí se alcanza después de abrir la sesión nativa y enlazar su
thread: broker_inference entra en async with native antes de entregar el facade.
Las cinco observaciones no fueron sólo preparación Ken. El nuevo ensayo cambia
el cliente/concurrencia; sigue enviando cero inferencias. Si no aparece el fallo,
conservar el resultado sin declarar la contención resuelta y documentar antes de
elegir otro experimento. El plan español con auditoría real Ken sigue pendiente;
no reintentar el proyecto 5 ni abrir una sucesión de variantes sin nueva evidencia.

El ensayo del navegador llegó a la guardia con 35 lecturas iniciadas, una admisión
y cero turnos; no reprodujo la contención. No se midió solapamiento en el servidor.
Los logs originales muestran procesos API distintos para el plan inglés y el
fallo español, con fuentes de bytes idénticos. Descartar la suposición de que ambos
ocurrieron necesariamente en la misma instancia viva del servicio.

Ruling: proteger primero el diagnóstico del productor. `_run` puede sustituir
el error por un conflicto con contexto suprimido durante retirada. Una prueba
kernel reproduce esa pérdida y requiere conservar ubicaciones seguras después del
cierre físico; otra impide que el sumidero roto controle el resultado. Se comparte
el extractor existente con el servicio, manteniendo su alias. No modifica CAS,
locks, reservas o el gate, ni afirma corregir el AuthorityBusy original.

88 casos de origen y los mismos 88 instalados pasan; 677 fuentes coinciden con
la rueda limpia y 9 definiciones están documentadas. Verificado a las 03:01:09 UTC,
32 min 39 s hasta verificar, sin documentación/checkpoint posteriores. Detalles de
estilo en DD129. [Alcance y siguiente investigación](../../modernization/native-startup-origin-review.md).
