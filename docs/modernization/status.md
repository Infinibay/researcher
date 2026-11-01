# Estado frente al plan de actualización

Fecha: 2026-11-01. Plan: [2026-10-31-actualizacion-proyecto.md](../superpowers/plans/2026-10-31-actualizacion-proyecto.md).
El objetivo completo sigue activo. Esta lista distingue componentes implementados
de fases cerradas; los pilotos y pruebas acotadas no completan la migración global.

## Realizado, con el alcance indicado

1. **Inventario y línea base:** dependencias, datos, arquitectura, inferencias,
   capacidades y fallas existentes documentadas. Se conservaron las 100 identidades
   de pruebas fallidas originales para detectar regresiones nuevas.
2. **Entorno reproducible:** dependencias fijadas, lock de Python/MCP, toolchains y
   build del frontend verificados. Arranque/import sin inferencia automática y
   resolución explícita de la base. La instalación final y restauración no están cerradas.
3. **Runtime de destino:** comparación inicial Codex/Infinidev y elección documentada
   de Codex CLI 0.166.0. Infinidev conserva resultados/limitaciones como alternativa,
   sin afirmar equivalencia de calidad, coste o cobertura de todos los gates.
4. **Ken y suscripción:** Ken publicado ken-rank 0.18.0 obligatorio en el camino nuevo,
   integrado en procesos aislados y probado realmente. Pruebas de inferencia por la
   suscripción, sin fallback silencioso a una API por uso. Falta migrar rutas auxiliares.
   Ken comprueba la identidad admitida al abrir su fuente y el CLI monta el caché
   público verificado. Búsqueda y lectura reales se comprobaron sin generación nueva.
5. **Primer recorrido de investigación:** tarea → lectura de código con Ken/adjunto o
   web → fuente capturada → hallazgo provisional/cita → informe draft persistido y
   consultable por API. No equivale a disponer de todas las capacidades de desarrollo.
6. **Control del recorrido nuevo:** identidad de intento, reservas/presupuestos,
   claves idempotentes, Stop/corrección, preguntas/respuestas y recuperación sin replay.
   Propiedad/cierre de procesos y comandos registrados probados; integración completa
   de consumidores heredados y efectos externos todavía pendiente.
   La sesión productiva ya ofrece start/read/cancel y Python de biblioteca estándar
   para análisis, con fuente en lectura, sin red ni credenciales heredadas. No habilita
   todavía edición, paquetes científicos ni entrega de gráficos/archivos.
   El propietario puede paginar los comandos y leer sus salidas guardadas, también
   tras perder autoridad el agente. Hay API y visor en la tarea y su historial.
7. **Contexto y procedencia:** versiones al corregir o cambiar trece entradas de tarea;
   retiro de autoridad antigua; respuesta asociada a pregunta/versión; repositorio
   admitido inmutable y comienzo de cola explícito. Registro exacto de la entrada
   inicial de Researcher, historia anterior acotada y clasificación de su procedencia.
   Dos turnos reales compararon base 137 con corrección a 200 sin repetir 137 en la nueva
   solicitud; ambos informes siguieron borrador y el registro original no cambió.
8. **Acceso del propietario:** sesión local, CSRF, separación entre usuario y grants de
   herramientas; el modelo no recibe cookie/credencial del propietario. Faltan clientes
   y superficies heredadas por migrar y aceptación completa en navegador.
9. **Interfaz inicial:** Tareas y Conversación tienen pilotos implementados; navegación
   responsive compartida, bandeja de preguntas por proyecto, historial, fuentes,
   correcciones y consulta de entrada. Existen 6/36 conceptos de escritorio y 2/12
   adaptaciones móviles, generados e inspeccionados, con selección razonada.
   **0/12 páginas tienen aceptación visual completa**. Playwright/Chromium ya ejecuta
   los pilotos: 8 estados de escritorio y 9 móviles pasan los controles automáticos;
   salto al contenido, foco y navegación se comprobaron. Falta aceptación integral.
10. **Migraciones/evidencia:** migraciones nuevas hasta versión 30, casos históricos,
    ensayos sobre copias sintéticas y comprobación de empaquetado. El último ensayo
    preservó 110 tablas, sus valores y rowids disponibles. No se migró una base del usuario.
11. **Revisión independiente inicial:** plan, escenarios y mapa de consumidores fueron
    analizados con contexto limpio. Hay 71 herramientas individuales en 11 categorías.
    Esa revisión no sustituye la revisión final de toda la rama implementada.

## Parcial o pendiente para completar el plan

1. **Reemplazo completo de engine/loop/autonomía/flows:** migrar todos los consumidores
   y retirar los loops LLM paralelos, incluyendo LoopEngine/CrewAI y configuración vieja.
2. **Todas las capacidades retenidas:** conectar las 71 herramientas/11 categorías al
   runtime/host correcto. Faltan edición/desarrollo productivo, consumidores de shell,
   coordinación entre agentes, búsqueda/documentos/PDF/CSV/DOCX/JSON/XML, wiki y otras
   rutas. Tener una primitiva o un mapa de migración no significa tenerlas integradas.
3. **Desarrollo y publicación completos:** tarea → cambio → pruebas → revisión
   independiente → aceptación sobre repo/base/head/contexto exactos → Git/PR/merge/CI,
   con reconciliación de efectos remotos inciertos y sin autoaprobar por terminar un turno.
4. **Prompts completos:** inventariar y revisar el 100% de roles, tareas, herramientas,
   resúmenes, memoria y protocolos. Hay guía y prompt mínimo del runtime revisado;
   faltan la aplicación integral de las skills de libros y sus reescrituras/evaluaciones.
5. **Comunicación evaluada:** casos reservados y comparación antes/después, comprensión
   observada con personas, esfuerzo del usuario, metáforas/diagramas accesibles y
   contenido estructurado seguro. Los casos numéricos actuales son evidencia parcial.
6. **Contexto más amplio:** revisar dependencias/proyecto/épicas/fuentes/archivos/Git/
   permisos, comandos tipados de edición con concurrencia/recibos y autoría verificada.
   Faltan checkpoints/compactación del historial largo; la entrada inicial registrada
   no incluye toda instrucción interna del proveedor ni resultados posteriores.
7. **Operación y aislamiento completos:** exclusión del workspace entre bases,
   alias/transferencia de propietario, restauración/despliegue con generación comprobada,
   lifecycle y borrado seguro de proyectos, presupuestos conservados y observabilidad.
8. **Datos e infraestructura final:** backup/restore completo, históricos reales,
   parsers/índices y servicios conservados —incluido decidir sus upgrades—, bootstrap,
   instalación limpia, CLI/TUI y documentación final de operación.
9. **Frontend restante:**30 conceptos de escritorio y 10 adaptaciones móviles; selección
   e implementación de las otras 10 rutas: inicio, proyectos, épicas, agentes, wiki,
   hallazgos, informes, archivos, repositorios y flujo. También paneles/diálogos compartidos.
10. **Aceptación de toda la web:** capturas comparables, móvil, teclado/foco, lector de
    pantalla, zoom, estados de error/espera/recuperación y E 2 E en las 12 páginas,
    incluidas las 2 que ya tienen piloto. Sincronización/catch-up, paginación y retención
    completas siguen pendientes. Build y SSR no sustituyen esas pruebas.
11. **Cierre técnico:** resolver o reemplazar correctamente las 100 fallas heredadas,
    completar checks y escenarios C/E/D/U del plan, revisión independiente final de
    toda la rama, retirada de código obsoleto y entrega verificable. No se hizo merge,
    push ni despliegue. El modelo se elige hoy por JSON global con reinicio; no hay
    selector web/per-agente/proyecto.

## Verificación más reciente

- Suite completa:1252 casos;1149 pasan,100 fallan con las mismas identidades de la
  línea base y 3 se omiten. La suite global sigue roja.
- Runtime:319 pasan. Frontend:28 pruebas aprobadas y compilación TypeScript/Vite
  tras los ajustes de contraste, cabecera móvil y navegación/foco.
- Ensayo real de continuidad:2 turnos por suscripción, Ken real,4 peers cerrados,
  fuentes sin editar,2 informes draft y ninguna aceptación/publicación implícita.
- Ensayo de análisis:1 turno adicional por suscripción, Ken real, catálogo de 15
  herramientas, cálculo ejecutado,1 informe draft y3 peers cerrados. El verificador
  inicial usó una columna incorrecta; se comprobaron los artefactos existentes sin
  repetir generación. CLI real sin inferencia:7 casos de cálculo/lectura/aislamiento.
- Inspección del propietario:servidor HTTP real sobre copia del ensayo anterior,
  sin runtime configurado ni inferencia nueva;14 lecturas reconstruyeron los95 bytes
  de salida. Nueve tablas conservaron sus valores tanto en original como en copia.
- QA visual:17 estados reales capturados e inspeccionados en Chromium con sandbox,
  sin infracciones detectadas por axe en esos estados. Se corrigieron carga same-origin,
  contraste, cabecera móvil, salto inicial y foco/desplazamiento entre secciones.
  Login, estados interactivos completos, lector de pantalla, zoom y comprensión humana
  siguen pendientes;0/12 rutas aceptadas. Dependencias:18 avisos npm preexistentes
  (5 bajos,3 moderados,10 altos), sin nuevos paquetes vulnerables por Playwright/axe.

Evidencia actual: [navegador](browser-evidence.json),
[recorrido visual](../design/audits/2026-11-01-owner-workspace/report.md),
[resultados actuales](browser-results.json), [entrada/continuidad](run-input-evidence.json),
[resultados](ken-identity-results.json), [identidad de Ken](ken-identity-evidence.json), [consulta del propietario](owner-command-evidence.json),
[análisis](analysis-evidence.json),
[ensayo de análisis](analysis-live.json), [continuidad](run-input-live.json),
[migración](run-input-migration.json), [cobertura](coverage.json),
[inventario visual](../design/inventory.md) y [registro de avance](progress.md).
