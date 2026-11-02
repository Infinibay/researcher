# Tablero de ejecución de la actualización

Actualizado: 2026-11-02. Objetivo: implementar **todo** el [plan](../superpowers/plans/2026-10-31-actualizacion-proyecto.md).
Este tablero organiza el trabajo; no reemplaza requisitos ni declara fases terminadas.
Motivos del ajuste: [diagnóstico del proceso](workflow-review.md).

## Estado comprobado

- Codex por suscripción y Ken publicado ensayados; fuentes/citas e informes draft conectados. Revisión documental independiente admitida y ensayada. Continúan consumidores y loops heredados, coordinación y desarrollo pendientes.
- Interfaz: 6 pilotos, 18/36 conceptos de escritorio y 6/12 móviles. Quedan seis rutas por implementar; 0/12 tienen aceptación completa.
- Última suite: 1878 casos: 1775 pasan, 100 fallos heredados y 3 omitidos. No hay fallos nuevos frente a la línea base; la suite sigue roja.
- Los 43 escenarios amplios continúan abiertos en [coverage.json](coverage.json). Se registran resultados y límites; no hay un porcentaje global defendible.

## Última entrega verificada: lectores y contexto de hallazgos

**Resultado:** los lectores retenidos de metadatos, texto/citas, resumen, búsqueda semántica y feedback usan los registros canónicos. No descartan la confianza desconocida por defecto; tarea y búsqueda no amplían el proyecto. Las decisiones reales son legibles sin dar permiso para emitirlas. El contexto diferencia omitir y borrar: un actor desconocido o retirado no hereda otro proyecto; los contextos asíncronos conservan su alcance.

**Conocimiento:** `FindingsKnowledgeSource` dejó de seleccionarse; sus llamadas antiguas fallan antes de leer o indexar y explican el destino de migración. No se borran los índices históricos. Semántica usa pesos locales preparados, texto completo, plaza por proceso y comprobación del corpus al terminar; no reutiliza BLOBs sin versión ni toma sólo los últimos 500. La búsqueda combinada informa cada fuente fallida y mantiene los resultados parciales, sin convertir el error en ausencia.

**Validación:** 37 casos nuevos, 80 dirigidos pasan. Paquete aislado: 160 pasan, 634 fuentes coincidentes; 22 archivos Python pasan Ruff lint/formato y 88 definiciones nuevas/modificadas están documentadas. Suite global: 1878 casos, 1775 pasan, los mismos 100 fallos heredados y 3 omitidos. Dos pruebas antiguas cambiaron de nombre; no se cuentan como casos nuevos.

**Reutilización de pruebas:** frontend sin cambios; se conserva el piloto y sus pruebas de la entrega anterior. No hubo nuevos turnos por suscripción. La revisión admitida que detectó 731 frente a 137 sigue documentada en [ensayo real](native-review-live.json).

[Contrato](../architecture/finding-readers.md), [resultados](finding-consumers-results.json), [paquete](finding-consumers-packaging.json), [docstrings](finding-consumers-docstrings.json).

**Siguiente acción:** completar el recorrido de revisión/aceptación del producto y retirar los writers, endpoints/CLI/MCP y flows heredados que todavía interpretan `VALIDATED`/`REJECTED`. La terminación del turno y la aceptación del resultado deben seguir separadas. Continuar desarrollo, roles/loops y comunicación tipada sin otro coordinador LLM. La invalidación de conocimiento dependiente permanece dentro del alcance.

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
- Ejecutar pruebas dirigidas durante el desarrollo. Si cambia bootstrap/importación de procesos, probar primero el wheel con el recorrido dirigido antes de lanzar la suite global. Ampliar al cambiar contratos compartidos, persistencia o fronteras de aislamiento; ejecutar la suite global al cerrar entregas y antes de la aceptación final. No repetirla sobre los mismos bytes por redactar documentación.
- Repetir un ensayo real sólo por un cambio relevante o una pregunta sin resolver. Conservar resultados parciales y comprobar el verificador sin inferencia antes de usar la suscripción.
- Reusar evidencia válida para la misma revisión/configuración. Un cambio de esos inputs invalida únicamente las conclusiones afectadas.
- Mantener aquí sólo estado actual y próximos resultados; detalles y logs en el ledger/evidencias. Al retomar: leer este tablero, el último bloque relevante y los archivos necesarios, sin reconstruir toda la historia.
- Reportar: resultado utilizable nuevo, criterio cumplido, bloqueo concreto y siguiente entrega. Contar commits/tests como validación o actividad, no como porcentaje del producto.
- Registrar por entrega tiempo transcurrido, esperas identificables, retrabajo y criterio aceptado. Recalibrar previsiones con las próximas dos entregas; no prometer una aceleración ni fecha sin esos datos.
