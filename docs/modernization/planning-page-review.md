# Planificación: aceptación técnica y visual

Página aceptada en su recorrido de propietario sobre el producto instalado.
Se combina la recuperación real de altas en `3d5928a` con el recorrido actual
de lectura, historia, borrado y fallos. **4/12 páginas**; siguen **41/43 escenarios**.
U08/C10, la contención original y la aceptación de otras páginas siguen abiertos.

El tramo observado de esta continuación va de **05:41:27 a05:47:49UTC,6min22s**,
incluida revisión de capturas; documentación/checkpoint posteriores excluidos.
El inicio original de esta tarea fue04:27:54UTC; ese tiempo de pared incluye
la primera fase y los intervalos entre continuaciones, no sólo trabajo activo.

## Qué se verificó

Instalación nueva, cuenta sintética, backend importado del entorno instalado;
ningún modelo ni proceso nativo lanzado. Dos historias de plan se preparan con
`ProjectPlans`, `SQLiteRunStore` y peers lógicos nunca lanzados y cerrados. Una
queda pendiente de revisión y otra aceptada mediante API de dominio. Son fixtures
de historia, **no planes generados ni una nueva aceptación humana**. Las lecturas
HTTP y los tres intentos de borrado sí son reales.

- Propuestas y aceptación guardadas, bases y suposiciones; enlace original con
  proyecto/tarea/run, seguido hasta la tarea correcta. Ninguna lectura acepta o
  ejecuta el plan. La explicación de entrada/salida es texto sintético ilustrativo;
  no acredita una mejora generada por el planificador ni cierra el feedback humano.
- Dependencia de las dos tareas manuales y agrupación por hito reales. Teclado:
  Enter abre la propuesta, foco entra al panel y vuelve al control del índice.
- Diálogo de borrado con objetivo explícito, foco inicial seguro y Escape. Historia
  nativa y grupo de plan aceptado devuelven409; borrado manual devuelve204. Tras
  recarga queda el grupo retirado, sus tareas sin asociaciones y las dependencias
  intactas; el resto de historia no cambia.
- Cortes de lectura de tareas, hitos, lista de propuestas y propuesta original:
  fallo visible, sin afirmar vacío como resultado correcto; recuperación explícita.
  Los cuerpos exitosos proceden del servicio, no de respuestas fabricadas.
- Respuesta real de grupos de A retenida y entregada tras cambiar aB; se espera
  su entrega antes de comprobar aislamiento. Vuelta aA,19grupos y descripción
  extensa. Después del borrado quedan18grupos y las seis tareas originales.

**14 estados,15 comprobaciones**,0errores de página,0violaciones Axe en regiones
analizadas, sin desbordamiento horizontal a1440/390px. No equivale a una auditoría
completa de accesibilidad, zoom nativo o comprensión humana. Tres funciones Python
y su módulo documentados en inglés; helpers del navegador documentados.

Servicio cerrado con143, guardián cerrado y dominio eliminado. Dos runs sintéticos
conservan estados needs_review/accepted;0despachos y0inicios nativos. Los cuatro
peers lógicos están cerrados; no se atribuye a ello retiro físico de actores.

El primer intento del evaluador falló porque la inyección apuntaba a una URL
incorrecta: se corrigió el evaluador. v2 pasó; v3 además espera la entrega tardía y
las lecturas finales del grupo extenso. No fue necesario modificar código de
producto ni reconstruir el paquete. Se usa el artefacto instalado y comprobado en
[planning-commands-packaging.json](planning-commands-packaging.json).

## Diseño y pendientes

Capturas actuales inspeccionadas frente a `tree-detail`: índice lateral, lectura
central, jerarquía tipográfica editorial y verde de acciones conservados. El móvil
separa índice y lectura; el botón de decisión original sigue visible al recorrer
la propuesta. Los mensajes de protección son claros y los fallos parciales no
ocultan qué consulta falló. La descripción extensa se lee sin recorte horizontal.

DD132 conserva densidad/cabecera móvil, texto técnico de red en inglés, vacíos de
consulta anterior y estilo; se añade un I001 del evaluador. No rehacer el diseño
por estos detalles. El badge global agrupa eventos del fixture y no significa
agentes activos. El pulido global de notificaciones queda para la fase final.

Evidencia: [resultados](planning-page-results.json),
[capturas y auditoría](../design/audits/2026-11-08-planning-acceptance/report.md),
[altas recuperables](planning-commands-review.md). Retenido localmente:
`.researcher/evaluations/planning-page-20261108-v3` (también v1/v2, sin reescribirlos).
No nueva suite global ni declaración de estilo verde. Siguiente capacidad: Resumen.
