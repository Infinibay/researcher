# Hallazgos: revisión original recuperada y conservada

Se completa la aceptación técnica y visual delegada de Hallazgos, uniendo los
lectores actuales, la búsqueda semántica positiva y este recorrido de revisión.
La decisión y los tres IDs de turno son fixtures sintéticos de dominio: no se
lanzó ningún modelo ni se evalúa aquí calidad científica o comprensión humana.

Sobre el wheel instalado c8a08615fa87ea7a7a05330f1d95af8ec1a87c3e565319307450a5d34d301d91,
el navegador recupera por HTTP202 la admisión original (misma clave/cuerpo/run),
lee decisión, límites, autor/revisor/contexto y captura original con hash. Un fallo
de lectura se muestra como desconocido; reintento y retorno de foco funcionan.
Stop202 cierra sólo ese intento y conserva la decisión y su historia. Recarga y
cambio de proyecto no reutilizan el enlace en otro proyecto.

**8 estados,11 comprobaciones**, escritorio1440/móvil390;0violaciones Axe regionales,
0desbordamiento y0errores de página. Sólo dos POST: recuperación y Stop. Antes/
después cambia exclusivamente el estado del revisor needs_review→cancelled; mismos
runs, tareas, peers cerrados, fuentes/hallazgos/informes y hashes.0dispatches antes/
después y3IDs de turno sintéticos nunca lanzados. Servicio termina143. Sin nueva
admisión generativa, aceptación de tarea, promoción del hallazgo o cuota consumida.

v1 esperaba nombre del autor donde el producto muestra ID del intento; v2 inyectaba
fallo en /sources en vez de /research-sources y capturaba un wrapper ausente al abrir
la fuente. Se corrigieron evaluadores siguiendo los contratos reales, sin tocar
producto; ambos resultados fallidos conservaron antes/después y se retomó el mismo
revisor. No se creó otro para ocultar el fallo. Originales retenidos.

Módulo y dos funciones Python documentados, helpers JS con JSDoc; sintaxis JS pasa.
Ruff conserva2I001/1F401 (DD137). No cambios de producto ni reconstrucción del wheel,
ni nueva suite global. Capturas inspeccionadas contra evidence-ledger: jerarquía,
registro lateral, lectura de límites/cita y móvil se conservan; densidad al final.

Tramo06:51:21–07:04:37UTC, **13min16s hasta verificar/inspeccionar**; documentación y
checkpoint posteriores excluidos. **8/12 páginas**,41/43 escenarios. U08/C10 siguen
abiertos; no nueva aceptación humana/científica. Restan Tareas, Conversación,
Ejecución, Proyectos/contención y gates globales. [Resultados](finding-review-page-results.json),
[capturas](../design/audits/2026-11-08-finding-review/report.md).
