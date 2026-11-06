# Retirada del motor de inferencia antiguo

Se elimina el paquete `backend.engine`: factory singleton, `LoopEngine`, cliente
LLM, pseudoherramientas, parser de llamadas, ejecutor paralelo, resúmenes y tracker
del último cambio. La inspección de imports en el código actual encontró sólo dos
consumidores de su excepción de parada; ambos pasan al módulo de control retenido.
Los recorridos de producto ya usaban el runtime nativo.

La migración de ejecución sigue siendo por solicitud del propietario, proyecto,
tarea e intento. Tareas y Conversación admiten trabajo en el runtime; Proyectos
prepara planes, y su aceptación y ejecución son decisiones separadas. El código
que todavía importe `backend.engine` debe migrar a esos casos de uso. No se ofrece
un sustituto síncrono que convierta un texto devuelto en aceptación.

| Responsabilidad retirada | Reemplazo existente |
| --- | --- |
| Loop de inferencia, reintentos y contexto del proveedor | Sesión nativa Codex admitida y sus límites; autenticación por suscripción |
| Pseudoherramientas y despacho por nombres/aliases | Catálogo nativo tipado y operaciones del host con autoridad por intento |
| “Último tracker” global | Candidato y evidencia ligados a ejecución e intento |
| Resumen inferido fuera del presupuesto | Entrada original conservada y política nativa; sin modelo auxiliar antiguo |
| `done` como texto de salida | Propuesta, comprobación, revisión y aceptación por separado |
| Excepción del engine usada para Stop | `LegacyControllerStopped` en `runtime.legacy_scope` |

## Historia y controladores existentes

No se cambia el esquema ni se borra ninguna fila. Checkpoints, mensajes,
asignaciones y etiquetas históricas siguen guardados; no se deserializan como un
loop ejecutable. La captura nativa de material previo sigue atribuyendo su origen.

FlowManager, AgentLoop y listeners conservan el control de trabajadores realmente
registrados. Una señal cooperativa interrumpe únicamente su proyecto; dejar un
scope restaura el anterior. Un timeout sigue conservando el hilo vivo. Retirar
el código de inferencia no demuestra cierre de procesos antiguos desconocidos.

## Pruebas y alcance

El [inventario de retirada](../modernization/engine-removal-inventory.json)
conserva hashes y nombres: doce módulos de producción, ocho archivos de pruebas,
157 funciones de prueba del algoritmo retirado. Se sustituyen además tres pruebas
de su antigua frontera por ausencia de módulos, cancelación por proyecto y guard
antes/después de admisión. La fixture de singleton ya no tiene un motor que resetear.
Es una retirada de pruebas obsoletas, **no una reparación de sus fallos**.

- RED inicial: dos fallos por módulos todavía disponibles y señal de parada aún
  no trasladada; el guard de proyecto ya pasaba.
- [Batería relacionada en fuente](../modernization/engine-removal-results.json):
  137 pasan y una falla, en 36,39 s. La prueba de migración54, sin modificar,
  instala también55 al omitir sólo54 y después espera53. Queda abierta en el
  bloque principal de migraciones; no se debilita ningún guard para hacerla pasar.
- [Paquete no editable](../modernization/engine-removal-packaging.json): 32 pasan,
  cero fallos/omisiones, 12,453 s; 814 fuentes coinciden con el wheel y 241 módulos
  se importan exclusivamente desde el entorno instalado. El archivo construido
  desde una copia limpia no contiene `backend/engine` ni sus pruebas.
- El entorno conserva 85 distribuciones nativas, sin CrewAI/LiteLLM. Dos turnos
  de producto con generación y Ken controlados comprueban investigación y
  planificación con kernel/broker/SQLite reales. Cero modelos reales o efectos
  sobre datos del usuario. No es evaluación de calidad de modelos o ranking.
- Ocho definiciones nuevas/modificadas tienen docstrings en inglés
  ([auditoría](../modernization/engine-removal-docstrings.json)). Dos pruebas del
  auditor de prompts pasan y su comprobación queda actualizada.

El inventario de prompts pasa a 560 candidatos en 500 archivos: se archivan 18 entradas
del engine eliminado. Dos revisiones de entrada se revalidaron porque el lector
de Agentes había cambiado el hash del módulo consumidor; su política y composición
no cambiaron. No se afirma eficacia por esta comprobación estática.

Siguen pendientes el catálogo/herramientas y dependencias legacy, configuración
obsoleta, exclusión física global, migraciones/restore, historial/presupuestos,
CLI y las evaluaciones integrales del plan. Los ajustes de estilo DD046 esperan
a que terminen esas capacidades principales.
