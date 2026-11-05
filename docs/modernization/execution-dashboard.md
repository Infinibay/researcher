# Tablero de ejecución de la actualización

Actualizado: 2026-11-05. Objetivo activo: implementar **todo** el [plan](../superpowers/plans/2026-10-31-actualizacion-proyecto.md). Este tablero no reemplaza requisitos ni declara el plan terminado. [Diagnóstico del proceso](workflow-review.md).

## Estado comprobado

- Codex por suscripción y Ken publicado ensayados. Fuentes/citas, informes draft y revisión documental independiente conectados. Desarrollo admitido desde Tareas/Conversación con captura y comprobaciones explícitas; revisión independiente solicitada desde Tareas y aceptación del propietario conectada. Faltan publicación y cutover de consumidores/loops antiguos.
- Interfaz: seis pilotos, 18/36 conceptos de escritorio y 6/12 móviles; seis rutas pendientes y 0/12 páginas completamente aceptadas.
- Última suite global completada al retomar `0c8b8d9`: 2148 casos, 2045 pasan, 100 fallan y tres se omiten. Mismos 100 identificadores heredados; no se afirman causas idénticas. Pasan 965 casos del runtime. La política Git añadida después tiene verificación separada.
- Los 43 escenarios amplios siguen abiertos en [coverage.json](coverage.json). No hay un porcentaje global defendible.

## Etapa actual: publicación con efecto y recibo propios

**Resultado parcial:** política Git interna con candidato exacto y metadatos de
origen/candidato fijados. La rama y el recibo ligado a la intención se guardan
atómicamente; un destino movido o una respuesta perdida no disparan otro efecto.
Los checkouts primarios/vinculados se rechazan. El estado histórico aplicado se
conserva aunque otro actor mueva después la rama.

**Verificación:** 38 casos dirigidos, incluidos 20 nuevos con Git real; 38 del wheel
en 4,92 segundos, 237 módulos sólo del paquete y 701 fuentes coincidentes.
39 definiciones nuevas documentadas en inglés. Tres regresiones observadas y
corregidas: consulta fallida tras commit, copia de `.git` con recibo aparentemente
válido y adopción del recibo con destino cambiado. No hubo llamadas a modelos.

**Pendiente inmediato:** admisión durable ligada a aceptación y tipo de ejecución
del host, claim/authority sin reabrir la tarea terminada; peers sólo de comandos;
launch/capsule con sólo `.git` escribible y stdin exacto en el manifiesto. Después,
controlador físico, API/Tareas y efectos remotos. El módulo nuevo no se expone
todavía como publicación del producto. [Contrato/debate](../architecture/code-publication.md),
[recibo](publication-policy-results.json), [paquete](publication-policy-packaging.json).

**Baseline completado:** al retomar se ejecutó el checkpoint previo con
`--timeout=180`, hasta salida terminal 1: 2045 pasan/100 heredados fallan/3 omitidos.
No se reinicia una suite sin comprobar su proceso. Este resultado no se atribuye
a la política nueva añadida después. [Alcance](resumed-baseline-results.json).

## Etapa anterior: entrada pública de desarrollo y revisión

**Resultado:** el adaptador con aislamiento admite `code`/`bug_fix`; los anteriores
conservan investigación. El host captura el candidato después del turno y ejecuta
recetas explícitas congeladas en las instrucciones originales. Captura o pipeline
fallidos no se ocultan detrás de un turno completado. Tareas solicita otro revisor
con el objeto exacto; cuerpo/clave sobreviven respuesta perdida y recarga.

**Verificación terminada:** diez casos dirigidos, con recorrido owner HTTP completo
hasta aceptación, comprobación real y origen intacto; 51 consumidores pasan.
Generación y Ken controlados, sin inferencia real nueva. Frontend 75 pruebas/build;
seis capturas inspeccionadas en tres anchos, cero errores de página/desbordamiento
y cero Axe en el panel nuevo. El navegador tiene procedencia física sintética y
retiene la revisión en cola; dos envíos idénticos dejan una admisión y ningún
intento nuevo. 22 definiciones Python documentadas; seis archivos pasan Ruff/formato.

**Paquete:** 84 casos pasan en el wheel ampliado; después se añadió sólo el
docstring faltante de `workspace`. Comparación completa de payloads/AST sin
docstrings y 11 casos del wheel final pasan; 698 fuentes coinciden.

**Verificación interrumpida para la pausa del propietario:** suite global. La primera invocación omitió el plazo de
integración y heredó 20 segundos; se detuvo con SIGINT/salida 2 y se reemplazó con
180 segundos. No se atribuyen sus timeouts al producto sin investigar. Las cifras
globales de arriba son históricas. La invocación corregida se detuvo mediante
SIGINT y terminó con salida 2 por petición explícita de pausa; no queda ejecutándose.
El propietario retomó el objetivo el 2026-11-05 y la nueva ejecución terminó;
su resultado y límites figuran en la etapa actual.
[Contrato](public-development.md),
[auditoría](../design/audits/2026-11-02-public-development/report.md).

**Siguiente entrega:** publicación reconciliable con nueva autoridad y validación
del destino exacto, conservando el veto de evidencia obsoleta o revisión rechazada.
Ninguna aceptación previa autoriza a reutilizar el dominio cerrado del autor.

**Checkpoint de publicación:** 35 casos dirigidos pasan tras reproducir cinco
entradas que el merge antiguo no rechazaba. Preflight de tarea/repositorio/origen
físico ahora bloquea esos casos y conserva repositorios legacy no relacionados.
No constituye exclusión entre procesos ni resuelve primera admisión concurrente;
el publicador reconciliable sigue pendiente. [Recibo](legacy-publication-results.json).
El propietario pidió commit/push de la rama y después pausa. Reanudó explícitamente
el objetivo el 2026-11-05; continúa activo.

## Etapa anterior verificada: aceptación explícita de código

**Resultado:** el propietario inspecciona commit/contexto, diff capturado, resultados
y revisión; acepta únicamente la observación exacta con reconocimiento de límites
cuando corresponda. Revisión rechazada/inconclusa/sin confirmar, fallos y trabajo
sin cerrar bloquean aceptación. Ausencia de pruebas nunca se etiqueta como éxito.
Recibo, evento y estados se guardan juntos; una corrección reabre la tarea y
conserva la decisión histórica. Publicación sigue separada y pendiente.

**Validación:** RED de contrato/almacenamiento y de lectura de captura en preparación;
111 casos compartidos pasan y dos integraciones reales de coordinador pasan con
generación controlada. Bootstrap del wheel: 50 pasan. Ampliación: 217 pasan sin
fallos ni omisiones en 349,94 segundos, 362 módulos sólo del paquete y 696 fuentes
coincidentes. Suite global anterior al ajuste final del historial: 2023 pasan, mismos 100 fallos heredados y tres
omisiones en 1090,75 segundos; no es una suite global verde. Las 66 definiciones
Python nuevas/modificadas tienen docstrings; 23 archivos pasan Ruff y 21 formato,
con deuda previa en los dos módulos grandes restantes.

**Interfaz:** 72 pruebas y build pasan. Once capturas, tres anchos, cero incidencias
Axe dentro del panel nuevo y cero errores de página. Dos envíos con cuerpo/clave
idénticos simulan pérdida antes y después del guardado: una aceptación y un evento
en SQLite; otra recarga recupera el recibo sin tercer envío. La inspección visual
detectó que campos pendientes vacíos no representaban el cuerpo guardado; nueva
prueba roja y corrección verifican casilla/nota originales. Se conservan ambos
recibos y capturas anteriores. No hay aceptación general de la página ni estudio
de comprensión; el fixture del navegador usa procedencia sintética explícita.

**Ajuste final:** una regresión demostró que una revisión favorable podía ocultar
una objeción anterior del mismo candidato. Ahora la objeción confirmada bloquea,
y la propuesta sin confirmar se conserva con su fuerza explícita. Historial
acotado sin omitir una cola; objeciones materiales ligadas a la huella. Pasan
30 casos dirigidos, 56 de bootstrap y 97 del wheel final en 131,24 segundos,
con 343 módulos sólo del paquete y 696 fuentes coincidentes. La captura once
verifica el desacuerdo visible y ausencia de aceptación. La suite global previa
no se atribuye a estos bytes; no hubo otra ejecución global.

[Contrato](code-acceptance.md), [resultados](code-acceptance-results.json),
[paquete](code-acceptance-packaging.json), [docstrings](code-acceptance-docstrings.json),
[auditoría](../design/audits/2026-11-02-code-acceptance/report.md).

**Continuación prevista entonces:** conectar la entrada pública de desarrollo al recorrido
existente de edición/captura/comprobaciones/revisión/aceptación y completar la
publicación reconciliable. La publicación debe revalidar código/destino y mantener
el veto de revisión rechazada o evidencia obsoleta. Continúan todas las obligaciones
de motor/roles/herramientas/comunicación/prompts/interfaz/operación del plan.
La entrada pública ya se conecta en la etapa actual; publicación sigue pendiente.

## Etapa anterior: revisión nativa del candidato

**Resultado:** otro actor/intento/hilo inspecciona el candidato en lectura, recibe petición/entrada originales y comprobaciones completas, y guarda una propuesta con citas y límites. Git se valida antes/después en el dominio original; tras cerrar sesión/herramientas/Ken, el host verifica otra vez las citas y confirma el protocolo. El coordinador retiene como fallo una terminación nativa sin confirmación. No acepta ni publica tareas.

**Verificación:** seis integraciones con generación controlada y Git/SQLite/kernel reales. Primer wheel: 336 pruebas pasan, sin fallos ni omisiones, en 718,39 segundos; 375 módulos sólo del paquete. Suite global de ese artefacto: 1993 pasan, 100 fallan y tres se omiten; 913 casos del runtime pasan. El ensayo real encontró que el índice reservado `.ken` invalidaba Git final. El ajuste limitado a dos archivos tuvo primero un fallo y dos casos que pasaban, y después 26 casos de Git/captura que pasan. Sólo permite estado raíz reservado no indexado; rechaza cambios de código, nombres similares y metadata indexada. Bootstrap final: 63 pasan. Wheel corregido: 83 pasan sin fallos ni omisiones en 302,80 segundos, incluidas las seis integraciones; 339 módulos sólo del paquete y 691 fuentes coincidentes. No se atribuye la suite global anterior a los bytes posteriores. Las 138 definiciones nuevas/modificadas tienen docstring; 38 archivos Python pasan Ruff, 36 formato, con deuda previa en los otros dos.

**Ensayo real:** suscripción, Codex 0.166.0, gpt-6.1-sol y ken-rank 0.18.0. Detectó 100,2 frente a 120, citó la fuente, explicitó limitaciones y registró `needs_revision`; protocolo confirmado, procesos cerrados y origen intacto. Autor/fallo controlados: no es evaluación representativa. Hubo dos turnos reales de revisor, incluido el anterior al ajuste que conservó propuesta sin confirmar. El fixture inicial del verificador cambió presupuesto y se rechazó antes de inferencia; se conserva su recibo. Ken find/read funcionaron; callers devolvió error y el revisor lo declaró como límite.

[Contrato](code-reviews.md), [resultados](native-code-review-results.json), [paquete final](native-code-review-packaging.json), [paquete anterior al ajuste](native-code-review-before-ken-fix-packaging.json), [ensayo real](native-code-review-live.json), [docstrings](native-code-review-docstrings.json).

**Continuación prevista en aquel checkpoint:** aceptación humana, publicación y admisión pública. La aceptación ya se integra en la etapa posterior descrita arriba; publicación y admisión pública siguen pendientes. Mantener el veto de revisión rechazada o evidencia obsoleta sobre publicación, y las decisiones humanas separadas de terminar un turno. Después, completar el cutover de los consumidores/loops antiguos, sin otro coordinador LLM. Todas las obligaciones restantes de comunicación, prompts, conocimiento, interfaz y operación siguen en alcance.

## Etapa anterior verificada: admisión e inspección de revisión

**Resultado implementado:** una revisión interna congela candidato, requisitos, autor/hilo originales y todas las comprobaciones. Exige otro actor, ejecución e hilo; conserva el repositorio original y monta el directorio del candidato en lectura. Revalida el objeto antes de abrir la puerta del proceso. Una comprobación pendiente sigue siendo desconocida y un resultado tardío que cambia la evidencia invalida la revisión actual, preservando la historia.

**Criterio de aquella etapa cumplido:** recibo sin repetición, objeto inmutable, procedencia cerrada, otro hilo, límites sin truncamiento silencioso, montaje real en lectura y corrección antes del despacho probados; migración 40 e inversa sin pérdida verificadas. En ese artefacto la sesión nativa de revisión estaba deshabilitada: su intento no congelaba entrada ni consumía presupuesto de inferencia.

**Validación:** 20 casos nuevos del protocolo y uno de fallo del recurso de migración. Los conjuntos dirigidos de 108, 109 y 20 casos pasan y se solapan. Bootstrap del wheel: 29 pasan en 7,55 segundos; ampliación posterior: 199 pasan en 86,16 segundos, sin fallos ni omisiones, con 350 módulos sólo del wheel y 679 fuentes coincidentes. Las 55 definiciones nuevas/modificadas están documentadas. No hubo una nueva suite global; la referencia histórica y los 100 fallos heredados siguen visibles arriba.

**Límites:** los fixtures de autor y Git son sintéticos; las dos pruebas de kernel demuestran montaje en lectura y rechazo antes del despacho. Faltan validación Git antes/después, sesión nativa, decisiones, aceptación/publicación y admisión pública. No hubo cambios de frontend/locks ni llamadas de modelo; los ensayos anteriores con suscripción/Ken conservan su alcance histórico.

[Contrato](code-reviews.md), [resultados y límites](code-review-state-results.json), [paquete](code-review-state-packaging.json), [docstrings](code-review-state-docstrings.json). El ejecutor de comprobaciones anterior conserva su [contrato y evidencias](code-checks.md).

La etapa nativa posterior descrita arriba reemplaza aquella siguiente acción; los recibos de admisión conservan su alcance histórico.

## Cola posterior, manteniendo el alcance

1. Completar investigación útil: migración de consumidores de búsqueda/documentos/conocimiento y revisión científica; migrar herramientas por capacidades, con sus prompts y contratos.
2. Desarrollo completo: edición/candidato, pruebas, revisión, Git/CI y efectos externos reconciliables. Resolver requisitos de aislamiento antes de habilitar cada efecto.
3. Migrar autonomía, roles, flows y comunicación entre agentes al mismo dueño durable; no añadir otro loop LLM. La comunicación humano–agente se verifica en cada recorrido.
4. Extender diseño a las demás páginas, con conceptos y selección por página; completar aceptación de los seis pilotos existentes.
5. Completar inventario/evaluaciones de todos los prompts y llamadas auxiliares, migraciones/restauración, dependencias, instalación, CLI/TUI y retirada del motor anterior. Trabajar estas obligaciones dentro de las entregas que las toquen; este orden no las aplaza todas al final.
6. Verificación global, revisión independiente de toda la rama y entrega. No cerrar el objetivo con un subconjunto.

## Reglas de ejecución desde este diagnóstico

- **Política explícita del usuario, 2026-11-05:** primero las capacidades principales. Si el resultado central de la tarea funciona, anotar los detalles secundarios en [detalles diferidos](deferred-details.md) y avanzar; resolverlos después, durante el pulido. No enroscarse en esos detalles ni ampliar el diseño por ellos. Al retomar o compactar contexto, leer esta regla antes de elegir la siguiente acción.
- Un recorrido activo. Como máximo, otro frente independiente con archivos y contrato separados; delegar investigación o trabajo definido, evitando revisiones genéricas recurrentes.
- Cada bloque declara resultado observable, criterio de salida, dependencias y pruebas necesarias **antes** de editar. Un experimento de 45–60 minutos sin resolver una incertidumbre exige reconsiderar la alternativa y registrar qué falta; no autoriza ignorar un requisito.
- Antes de ampliar infraestructura, identificar el escenario obligatorio y el fallo reproducido que bloquea el recorrido. Si no lo bloquea, asignarle una entrega posterior y una prueba, conservándolo en el plan.
- Ejecutar pruebas dirigidas durante el desarrollo. Si cambia bootstrap/importación de procesos, probar primero el wheel con el recorrido dirigido. Ampliar a los consumidores afectados al cambiar contratos compartidos, persistencia o aislamiento. Las etapas internas conservan evidencia de ese alcance; ejecutar la suite global al integrar un recorrido de producto y antes de la aceptación final. No sustituir la aceptación global por estas etapas ni repetir una suite sobre los mismos bytes por redactar documentación.
- Repetir un ensayo real sólo por un cambio relevante o una pregunta sin resolver. Conservar resultados parciales y comprobar el verificador sin inferencia antes de usar la suscripción.
- Reusar evidencia válida para la misma revisión/configuración. Un cambio de esos inputs invalida únicamente las conclusiones afectadas.
- Mantener aquí sólo estado actual y próximos resultados; detalles y logs en el ledger/evidencias. Al retomar: leer este tablero, el último bloque relevante y los archivos necesarios, sin reconstruir toda la historia.
- Reportar: resultado utilizable nuevo, criterio cumplido, bloqueo concreto y siguiente entrega. Contar commits/tests como validación o actividad, no como porcentaje del producto.
- Registrar por entrega tiempo transcurrido, esperas identificables, retrabajo y criterio aceptado. Recalibrar previsiones con las próximas dos entregas; no prometer una aceleración ni fecha sin esos datos.
