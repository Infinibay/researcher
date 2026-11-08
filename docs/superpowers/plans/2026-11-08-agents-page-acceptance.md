# Aceptación de Agentes

Inicio05:55:41UTC, base444af41. Concepto existente `roster`; reutilizarlo.

1. Leer AgentLedger, WorkBudget y RunAttempts con APIs reales; no roster antiguo.
2. Reusar fixtures de dominio de Resumen y añadir27runs terminales sintéticos
   para paginación25+5. Un recibo sintético de consumo55/modelo explícitamente
   sintético prueba presentación de observaciones; no inferencia o facturación.
3. Host nuevo instalado/cuenta sintética. Comprobar entrada/vacío, identidad,
   enlace original, datos desconocidos y recibos de intento/modelo/presupuesto.
4. Edición real de presupuesto: perder respuesta después del commit, recargar y
   recuperar por GET el recibo original, sin otro POST ni generación. Stop sobre
   pregunta sintética cerrada: corte antes del envío y luego después del commit,
   observar resultado por lectura sin atribuir cierre a la respuesta perdida.
5. Fallos parciales, recuperación, proyectoA→B→A y respuesta tardía. Escritorio,
   móvil y teclado, Axe regional; comparar capturas con roster. Detalles al final.
6. Verificar conservación de historia,0modelos lanzados y cierre del servicio;
   documentar IDs de turno/consumo sintéticos sin llamarlos evidencia de ejecución.

No editar producto salvo fallo funcional demostrado. Docstrings/JSDoc en inglés.
U08/C10, contención original y demás gates globales continúan.

## Resultado

06:01:59UTC,6min18s hasta verificar/inspeccionar:11estados/13comprobaciones pasan.
30runs/5actores,25+5; un cambio real de presupuesto recuperado por GET tras perder
el recibo y un Stop202real observado por lectura tras perder la respuesta.
Historia/consumo/turno sintéticos no equivalen a inferencia. Servicio143/dominio
eliminado. Dos errores del evaluador corregidos (retiro sintético y expectativa
200vs202), sin cambiar producto.6/12páginas,41/43escenarios; DD134al final.
[Evidencia](../../modernization/agents-page-review.md).
