# Tablero de ejecución de la actualización

Actualizado: 2026-11-02. Objetivo: implementar **todo** el [plan](../superpowers/plans/2026-10-31-actualizacion-proyecto.md).
Este tablero organiza el trabajo; no reemplaza requisitos ni declara fases terminadas.
Motivos del ajuste: [diagnóstico del proceso](workflow-review.md).

## Estado comprobado

- Codex por suscripción y Ken publicado ensayados; fuentes/citas e informes draft conectados. Revisión documental independiente admitida y ensayada. Continúan consumidores y loops heredados, coordinación y desarrollo pendientes.
- Interfaz: 6 pilotos, 18/36 conceptos de escritorio y 6/12 móviles. Quedan seis rutas por implementar; 0/12 tienen aceptación completa.
- Última suite: 1841 casos: 1738 pasan, 100 fallos heredados y 3 omitidos. No hay fallos nuevos frente a la línea base; la suite sigue roja.
- Los 43 escenarios amplios continúan abiertos en [coverage.json](coverage.json). Se registran resultados y límites; no hay un porcentaje global defendible.

## Última entrega verificada: revisión ligada a versión y feedback

**Resultado:** el propietario admite un revisor con hilo, intento y permisos distintos del autor. Se congela la versión del hallazgo y se conservan citas, contraevidencia, procedencia y límites. Una modificación pierde la atribución a su autor original si no coincide con su sello; una revisión anterior no se transfiere al texto nuevo. El autor puede leer feedback mediante su permiso ordinario, sin obtener permiso para decidir revisiones.

**Interfaz:** el piloto de Hallazgos muestra primero la afirmación, luego la decisión, sus comprobaciones y limitaciones; permite solicitar/cerrar un intento, consultar historial y abrir la captura con el hash revisado. Distingue versión anterior y vigencia desconocida. El reenvío tras perder una respuesta conserva el paquete original, incluso tras recargar. Nueve estados funcionales y tres anchos finales sin infracciones de axe; aceptación integral todavía pendiente.

**Validación:** 36 casos nuevos; regresión dirigida 939 pasan. Wheel aislado: 488 pasan y 1 fallo heredado explícito; 628 fuentes coincidentes. Frontend: 57 pasan y build correcto. Suite global: 1841 casos, 1738 pasan, los mismos 100 fallos heredados y 3 omitidos. Auditoría local: 122 definiciones Python nuevas/modificadas con docstrings; no sustituye la auditoría de toda la rama.

**Ensayo real:** un revisor `gpt-6.1-sol` con tu suscripción y Ken publicado detectó 731 frente a 137 y registró «Requiere cambios», con citas y límites; un turno. La generación del autor fue controlada y sintética. Sin promoción del hallazgo/informe/tarea; cierre de permisos, peers y dominio comprobado. Este resultado no acredita calidad científica general.

[Contrato](../architecture/finding-reviews.md), [resultados](review-results.json), [paquete](review-packaging.json), [ensayo y límites](native-review-live.json), [prueba visual](../design/audits/2026-11-02-finding-review/report.md).

**Siguiente acción:** migrar consumidores heredados de validación, rechazo y conocimiento a este contrato, incluyendo feedback e invalidación de dependencias. Después, continuar la migración de roles/flows por capacidades y los recorridos de desarrollo. No cerrar el objetivo con la revisión de un único hallazgo.

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
