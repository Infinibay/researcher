# Presupuesto de herramientas independiente de los avisos

Se corrigió un fallo funcional del engine: el conteo dependía de
`item/started`, pero las solicitudes reales `item/tool/call` podían ejecutar
efectos sin esos avisos. La sesión ahora reserva cupo antes del callback,
comparte identidad con inicio/finalización y rechaza solicitudes repetidas.
Una finalización duplicada tampoco reinicia el plazo sin progreso.
[Contrato y ejemplo](../architecture/host-tool-budget.md).

## Evidencia

Bloque iniciado el **7 de noviembre de 2026, 15:27:51 UTC**; validación observada
completa a las **15:44:08 UTC**, **16 min 17 s**. La documentación y el checkpoint
posteriores no están incluidos en ese tiempo.

- El ensayo previo produjo nueve fallos y dos aprobados: faltaban límites ante
  avisos ausentes/tardíos, identidades repetidas o ausentes, y conteo entre turnos.
- Pasan **101 casos distintos de fuente**. Incluyen RPC real con proceso hijo,
  finalizaciones sin inicio, duplicados, orden invertido, dos turnos y regresión
  de planificación, desarrollo, revisión y entrega atómica.
- Pasan **84 casos instalados fuera del checkout**, sin fallos ni omisiones.
  Coinciden **624 archivos** entre fuente, wheel e instalación, **329 de producto**;
  los 233 módulos backend cargados provienen del entorno instalado.
  [Recibo de instalación](host-tool-budget-packaging.json).
- El recorrido con kernel, broker y SQLite reales admite seis herramientas,
  guarda una fuente, un hallazgo y un informe borrador; bloquea la séptima antes
  de proponer el resultado. Quedan cero propuestas, aceptaciones y permisos
  activos, con todos los peers cerrados. Se registra un único despacho de
  inferencia controlada. El aviso al usuario identifica el límite de herramientas
  y propone inspeccionar el trabajo conservado, sin repetir el intento.
  [Observaciones](host-tool-budget-native-observations.json).
- Las **24 definiciones** del módulo productivo, incluido el módulo, tienen
  docstring. El inventario mantiene 85 candidatos revisados y ninguna revisión
  pendiente; no se modificaron decisiones semánticas de prompts.

Las fixtures se ajustaron para enviar identidades reales del protocolo. La del
host completo asigna una identidad por solicitud, incluso cuando consulta varias
veces el mismo paso. No se relajó ningún control del producto.

[Resultados reproducibles y hashes de recibos](host-tool-budget-results.json).

## Alcance pendiente

La generación y Ken fueron controlados; **no hubo consumo de modelos**. La
deduplicación request/item está respaldada por código y pruebas oficiales del
runtime fijado, no por una suposición sobre avisos opcionales.

E07/E08 siguen abiertos para su aceptación integral: el presupuesto agregado por
operación, intento y proyecto, la recuperación y los demás escenarios de consumo
y falta de progreso requieren contrastar lo ya implementado con sus pruebas.
La asignación de la última observación de tokens, ante avisos atrasados, es una
hipótesis para revisar; no se registra todavía como defecto demostrado.

Este bloque no convierte observaciones nativas tardías en prevención de efectos
ya ocurridos. Tampoco acredita comprensión humana, calidad de modelos, aceptación
de páginas o una suite global nueva. Siguen **42 escenarios amplios abiertos** y
**0/12 páginas completamente aceptadas**. Los detalles secundarios se atienden
después de todas las capacidades principales.
