# Tablero de ejecución de la actualización

Actualizado: 2026-11-02. Objetivo: implementar **todo** el [plan](../superpowers/plans/2026-10-31-actualizacion-proyecto.md). Este tablero no reemplaza requisitos ni declara el plan terminado. [Diagnóstico del proceso](workflow-review.md).

## Estado comprobado

- Codex por suscripción y Ken publicado ensayados. Fuentes/citas, informes draft y revisión documental independiente conectados. Desarrollo interno edita, captura y comprueba candidatos exactos; ahora también registra revisión nativa separada. Faltan aceptación, publicación, admisión pública y cutover de consumidores/loops antiguos.
- Interfaz: seis pilotos, 18/36 conceptos de escritorio y 6/12 móviles; seis rutas pendientes y 0/12 páginas completamente aceptadas.
- Última suite global: 2096 casos, 1993 pasan, 100 fallan y tres se omiten. Mismos 100 identificadores heredados, sin fallos nuevos por identidad; no se afirman causas idénticas. Esa ejecución empezó antes del ajuste final de `.ken`, validado por separado.
- Los 43 escenarios amplios siguen abiertos en [coverage.json](coverage.json). No hay un porcentaje global defendible.

## Última etapa verificada: revisión nativa del candidato

**Resultado:** otro actor/intento/hilo inspecciona el candidato en lectura, recibe petición/entrada originales y comprobaciones completas, y guarda una propuesta con citas y límites. Git se valida antes/después en el dominio original; tras cerrar sesión/herramientas/Ken, el host verifica otra vez las citas y confirma el protocolo. El coordinador retiene como fallo una terminación nativa sin confirmación. No acepta ni publica tareas.

**Verificación:** seis integraciones con generación controlada y Git/SQLite/kernel reales. Primer wheel: 336 pruebas pasan, sin fallos ni omisiones, en 718,39 segundos; 375 módulos sólo del paquete. Suite global de ese artefacto: 1993 pasan, 100 fallan y tres se omiten; 913 casos del runtime pasan. El ensayo real encontró que el índice reservado `.ken` invalidaba Git final. El ajuste limitado a dos archivos tuvo primero un fallo y dos casos que pasaban, y después 26 casos de Git/captura que pasan. Sólo permite estado raíz reservado no indexado; rechaza cambios de código, nombres similares y metadata indexada. Bootstrap final: 63 pasan. Wheel corregido: 83 pasan sin fallos ni omisiones en 302,80 segundos, incluidas las seis integraciones; 339 módulos sólo del paquete y 691 fuentes coincidentes. No se atribuye la suite global anterior a los bytes posteriores. Las 138 definiciones nuevas/modificadas tienen docstring; 38 archivos Python pasan Ruff, 36 formato, con deuda previa en los otros dos.

**Ensayo real:** suscripción, Codex 0.166.0, gpt-6.1-sol y ken-rank 0.18.0. Detectó 100,2 frente a 120, citó la fuente, explicitó limitaciones y registró `needs_revision`; protocolo confirmado, procesos cerrados y origen intacto. Autor/fallo controlados: no es evaluación representativa. Hubo dos turnos reales de revisor, incluido el anterior al ajuste que conservó propuesta sin confirmar. El fixture inicial del verificador cambió presupuesto y se rechazó antes de inferencia; se conserva su recibo. Ken find/read funcionaron; callers devolvió error y el revisor lo declaró como límite.

[Contrato](code-reviews.md), [resultados](native-code-review-results.json), [paquete final](native-code-review-packaging.json), [paquete anterior al ajuste](native-code-review-before-ken-fix-packaging.json), [ensayo real](native-code-review-live.json), [docstrings](native-code-review-docstrings.json).

**Siguiente entrega:** aceptación humana del candidato exacto, publicación reconciliable y admisión pública, integradas con los contratos existentes de desarrollo/comprobaciones/revisión. Mantener el veto de revisión rechazada o evidencia obsoleta sobre publicación, y las decisiones humanas separadas de terminar un turno. Después, completar el cutover de los consumidores/loops antiguos, sin otro coordinador LLM. Todas las obligaciones restantes de comunicación, prompts, conocimiento, interfaz y operación siguen en alcance.

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

- Un recorrido activo. Como máximo, otro frente independiente con archivos y contrato separados; delegar investigación o trabajo definido, evitando revisiones genéricas recurrentes.
- Cada bloque declara resultado observable, criterio de salida, dependencias y pruebas necesarias **antes** de editar. Un experimento de 45–60 minutos sin resolver una incertidumbre exige reconsiderar la alternativa y registrar qué falta; no autoriza ignorar un requisito.
- Antes de ampliar infraestructura, identificar el escenario obligatorio y el fallo reproducido que bloquea el recorrido. Si no lo bloquea, asignarle una entrega posterior y una prueba, conservándolo en el plan.
- Ejecutar pruebas dirigidas durante el desarrollo. Si cambia bootstrap/importación de procesos, probar primero el wheel con el recorrido dirigido. Ampliar a los consumidores afectados al cambiar contratos compartidos, persistencia o aislamiento. Las etapas internas conservan evidencia de ese alcance; ejecutar la suite global al integrar un recorrido de producto y antes de la aceptación final. No sustituir la aceptación global por estas etapas ni repetir una suite sobre los mismos bytes por redactar documentación.
- Repetir un ensayo real sólo por un cambio relevante o una pregunta sin resolver. Conservar resultados parciales y comprobar el verificador sin inferencia antes de usar la suscripción.
- Reusar evidencia válida para la misma revisión/configuración. Un cambio de esos inputs invalida únicamente las conclusiones afectadas.
- Mantener aquí sólo estado actual y próximos resultados; detalles y logs en el ledger/evidencias. Al retomar: leer este tablero, el último bloque relevante y los archivos necesarios, sin reconstruir toda la historia.
- Reportar: resultado utilizable nuevo, criterio cumplido, bloqueo concreto y siguiente entrega. Contar commits/tests como validación o actividad, no como porcentaje del producto.
- Registrar por entrega tiempo transcurrido, esperas identificables, retrabajo y criterio aceptado. Recalibrar previsiones con las próximas dos entregas; no prometer una aceleración ni fecha sin esos datos.
