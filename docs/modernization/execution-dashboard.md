# Tablero de ejecución de la actualización

Actualizado: 2026-11-02. Objetivo: implementar **todo** el [plan](../superpowers/plans/2026-10-31-actualizacion-proyecto.md).
Este tablero organiza el trabajo; no reemplaza requisitos ni declara fases terminadas.
Motivos del ajuste: [diagnóstico del proceso](workflow-review.md).

## Estado comprobado

- Codex por suscripción y Ken publicado ensayados; fuentes/citas e informes draft conectados. Revisión documental independiente admitida y ensayada. Desarrollo interno ya edita, captura candidatos exactos y ejecuta comprobaciones aisladas; faltan revisión de código, aceptación, publicación y entrada pública. Continúan consumidores y loops heredados y coordinación pendientes.
- Interfaz: 6 pilotos, 18/36 conceptos de escritorio y 6/12 móviles. Quedan seis rutas por implementar; 0/12 tienen aceptación completa.
- Suite del primer artefacto del ejecutor: 2039 casos, 1933 pasan, 103 fallan y 3 se omiten. Las tres regresiones nuevas de importación se corrigieron después: 36 pruebas dirigidas y 393 del wheel final pasan. El resultado global anterior conserva sus 103 fallos; no hubo una segunda suite completa tras corregir esa importación. Los 100 fallos heredados siguen pendientes.
- Los 43 escenarios amplios continúan abiertos en [coverage.json](coverage.json). Se registran resultados y límites; no hay un porcentaje global defendible.

## Última entrega verificada: comprobaciones del candidato exacto

**Resultado implementado:** cada receta se reserva antes de producir efectos y ejecuta en una copia separada del commit/árbol capturados, con Git de validación protegido. El host conserva receta, candidato, salida, JUnit, operación, cierre y resultado durable. Repetir una clave no lanza otra comprobación. Una modificación del código invalida el resultado; Stop o una corrección conservan el trabajo interrumpido sin aprobarlo bajo otro contexto.

**Criterio de salida cumplido:** ejecución real de pytest, resultados distintos para fallo/cero pruebas/omitidas, copia de origen intacta, detección de cambios, Stop y contexto obsoleto cubiertos; migración y paquete verificados. Las comprobaciones no dan permiso para publicar.

**Validación:** 22 casos nuevos; 99 pruebas previas de migración/estado/puertos y tres integraciones pasan. El wheel final verifica 393 casos sin fallos ni omisiones, 386 módulos sólo del paquete y 676 fuentes coincidentes. Las tres regresiones de recuperación del primer artefacto quedaron corregidas con 36 pruebas dirigidas; la comparación de AST demuestra que el único cambio posterior fue diferir la importación del parser hasta el registro del resultado. Las 98 definiciones nuevas/modificadas están documentadas. Las 16 combinaciones previas del filtro de syscalls conservan sus mismos bytes.

**Límites:** entornos `system` y `runtime-python` elegidos por host, sin instalación ni acceso a Internet; identidad física del directorio de dependencias, sin fijar todos sus bytes. Presupuestos separados por fase. Sin cambios de frontend ni nuevas llamadas de modelo; los ensayos anteriores con suscripción/Ken conservan su alcance histórico.

[Contrato](code-checks.md), [resultados y límites](owned-checks-results.json), [paquete](owned-checks-packaging.json), [docstrings](owned-checks-docstrings.json).

**Siguiente acción:** implementar revisión independiente de código y aceptación/publicación del mismo candidato antes de habilitar desarrollo público. Mantener pendientes la migración de writers/consumidores de hallazgos, roles/loops y comunicación tipada, sin añadir otro coordinador LLM. La invalidación de conocimiento dependiente permanece dentro del alcance.

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
