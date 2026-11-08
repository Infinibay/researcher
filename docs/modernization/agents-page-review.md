# Agentes: registro, presupuesto y parada verificados

**6/12 páginas** en alcance técnico/visual delegado; **41/43 escenarios amplios**.
Tramo05:55:41–06:01:59UTC, **6min18s** hasta verificar/inspeccionar, incluida
corrección del evaluador. Documentación/checkpoint posteriores excluidos.

## Recorrido comprobado

Host nuevo, backend instalado y frontend existente. Datos de historia preparados
por APIs de dominio, HTTP/SQLite reales y ninguna respuesta exitosa inventada.
Un ID de turno y un recibo de dispatch/consumo55 son **sintéticos**. Ningún modelo
ni peer nativo se lanzó; estos registros no acreditan consumo o cierre físico.
Los nombres synthetic-never-launched hacen explícita la procedencia del ejemplo.

- Entrada sin selección;30runs/5actores reales en la base de prueba, paginación
  HTTP25+5 y selección por teclado con retorno de foco. Ningún roster antiguo.
- Tarea original con proyecto/ID, intento y resultado originales consultados por
  HTTP. Modelo para el envío del recibo sintético visible; las otras observaciones
  ausentes siguen «No disponible»/«Sin envío registrado», sin inventar cero o cuota.
- Presupuesto real200→1000tokens y2→4turnos, una revisión0→1 y un único recibo.
  Se pierde la respuesta **después** del commit; recarga conserva el paquete y
  «Consultar recibo original» recupera por GET, sin otro POST ni ejecución.
- Stop sobre la pregunta sintética ya aparcada: primer envío no reenviado, error
  visible y estado esperando respuesta. Segundo envío llega al servicio, devuelve
 202y se pierde su respuesta; lectura posterior muestra cancelled, conserva el
  mismo run y retira el botón. No se presenta el error de entrega como recibo de
  cierre; no se cambian otras ejecuciones, tareas, grupos, dependencias o peers.
- Fallos independientes de registro/presupuesto, sin falso registro vacío;
  recuperación explícita. Respuesta original deA entregada después de cambiar aB,
  esperada antes de comprobar queBno hereda filas/selección; vuelta aA correcta.

**11estados/13comprobaciones**,0errores de página,0violaciones Axe regionales,
sin desbordamiento1440/390px. Servicio143, guardián cerrado/dominio eliminado.
Los peers son recibos lógicos preparados/nunca lanzados y cerrados.0modelos reales;
un ID de turno y un recibo de dispatch sintéticos se mantienen antes/después.
Las tres funciones y módulo del evaluador llevan docstrings; helpers JS con JSDoc.
Sintaxis JS pasa, I001enDD134. No nueva suite global ni declaración de estilo verde.

v1del evaluador omitía retirar el turno fallido sintético y quedaba reconciling:
se corrigió usando retire_inference tras cerrar los peers. v2esperaba200en Stop,
pero el endpoint correctamente usa202; se corrigió la expectativa. No se relajó
la política del producto ni se repitió trabajo real; originales/logs retenidos.

## Revisión visual y alcance

Capturas actuales inspeccionadas frente a `roster`: índice/detalle, agente/tarea,
estado guardado y consumo, controles separados y lectura móvil conservados.
El presupuesto compartido desplaza bastante el registro; reducir densidad al final,
sin rehacer diseño ni duplicar mecanismos. El error de entrega de Stop puede
coexistir con cancelled leído después: ajustar su texto para distinguir consulta
actual y respuesta original enDD134. No comprensión humana atribuida.

Esta página acredita el registro/control descrito. La lista de procesamiento local
compartida no tiene jobs en este fixture y conserva sus gates de trabajo auxiliar.
No modelo efectivamente ejecutado ni medición de suscripción. U08/C10/AuthorityBusy
siguen abiertos. Se reutiliza el paquete de
[planning-commands-packaging.json](planning-commands-packaging.json), sin cambios
productivos ni rebuild redundante. [Resultados](agents-page-results.json),
[capturas](../design/audits/2026-11-08-agents-acceptance/report.md).
Siguiente: Hallazgos e Informes, reutilizando fuentes y recibos de dominio.
