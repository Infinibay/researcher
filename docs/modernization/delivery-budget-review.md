# Presupuesto visible, entrega y trabajo parcial

Base `ab36dc5`; bloque iniciado el 7 de noviembre de 2026 a las 09:29:55 UTC.
El cambio atiende los fallos de [la evaluación por perfiles](profile-communication-review.md).
No declara aceptada la comunicación general ni sustituye sus respuestas originales.

## Comportamiento implementado

- El host incluye los límites efectivos en las instrucciones congeladas antes
  del turno. El catálogo4 conserva la identidad histórica de catálogos2/3.
- Cada respuesta de una herramienta dinámica incorpora, en un elemento separado,
  tiempo transcurrido, herramientas observadas, tokens observados y margen restante.
  Conserva el resultado original de la herramienta. Los valores desconocidos
  siguen siendo desconocidos; la información no es facturación ni cuota de cuenta.
- El último cuarto del presupuesto aconseja cerrar y explicar. Es orientación,
  no una reserva garantizada: los eventos pueden llegar tarde y las herramientas
  nativas sin respuesta del host no reciben esta actualización. Los límites duros,
  permisos, cancelación, comprobaciones obligatorias y decisiones de aceptación
  mantienen su comportamiento.
- Una interrupción por herramientas, tokens, tiempo, falta de progreso, tamaño de
  respuesta o turnos conserva la causa estructurada y el presupuesto observado.
  El aviso del propietario indica que puede existir trabajo parcial y pide revisar
  sus artefactos; no convierte un borrador en entrega ni repite el intento.
- La política común acota descubrimiento improductivo y exige ejemplos al nivel
  de la evidencia: una media de grupo no demuestra el cambio de cada individuo.
  Las ilustraciones hipotéticas deben identificarse como tales.

## Validación y límites

Las pruebas dirigidas incluyen respuestas reales del protocolo, deduplicación de
eventos, tokens desconocidos, límites que siguen interrumpiendo, ausencia de reintento,
identidad de instrucciones y un informe real guardado antes de una interrupción.
El informe permanece `draft`, sin resultado entregado ni aceptación.
Pasan **132 casos distintos de fuente y 80 del paquete instalado**, sin fallos
ni omisiones. Coinciden 608 archivos entre fuente, wheel e instalación; 324 son
productivos. Las 33 definiciones cambiadas y diez módulos tienen documentación.
Se conservan los [resultados dirigidos](delivery-budget-results.json) y los
[docstrings comprobados](delivery-budget-docstrings.json).
Los [recibos del paquete](delivery-budget-packaging.json) verifican la instalación
fuera del checkout. Las pruebas automáticas no demuestran comprensión humana.

Se registraron antes de ejecutar tres comprobaciones de desarrollo con los casos
ya observados: planificación, auditoría y medias de grupos. Un turno nuevo por caso,
misma suscripción, límites anteriores de120000/350000/350000tokens y20herramientas,
sin aumentar los techos del operador. Los casos antes reservados ahora son
regresiones de desarrollo; no se presentan como nuevos casos reservados ni como
comparación causal con el baseline. No se repite una respuesta fallida.

El primer resultado vuelve a agotar los tokens en planificación: conserva una
propuesta, pero no una explicación final. El aviso nuevo sí muestra la causa y
el trabajo parcial. Esto deja pendiente la entrega dentro de ese presupuesto;
no justifica elevarlo automáticamente ni declarar resuelto el caso.

| Caso nuevo | Resultado observado | Tokens observados | Tiempo del brazo |
| --- | --- | ---: | ---: |
| Planificación | Una propuesta guardada; sin explicación final por límite de tokens | 135796 / 120000 | 61,180 s |
| Auditoría | Informe y explicación entregados; fallo reproducido y alcance explícito | 346386 / 350000 | 89,093 s |
| Medias de grupos | Informe y explicación entregados; 80→79,2, sin atribuir cambios individuales | 305543 / 350000 | 97,675 s |

Tres servicios y todos los peers registrados cerraron, sin concesiones locales
activas. Dos consumos quedaron asentados y uno desconocido; no se inventa consumo
final por haber cerrado procesos. Se verificaron hashes, citas exactas, integridad
de bases, ausencia de aceptación/publicación y fuentes originales sin cambios.
La suma es 247,948 segundos y 787725 tokens observados, no coste facturado.
[Recibos reales](delivery-budget-live.json) y [respuestas completas](delivery-budget-responses.json).

La auditoría todavía cometió y corrigió un nombre de función erróneo en su primer
diagnóstico; lo declara. El ejemplo científico distingue las contribuciones de
las medias de cambios individuales. Estas lecturas del implementador no son
evaluación ciega ni prueba de comprensión humana o fiabilidad general.

## Revisión de prompts y detalles posteriores

La revisión del cambio comprende 16 decisiones cuyo texto o consumidor cambió;
67 mantienen sus dependencias y todas las revisiones previas se conservan.
El inventario vuelve a tener 83 decisiones estáticas vigentes. Los cambios de
consumidores se acotan al catálogo común y su conexión en el factory: no se
reinterpreta la revisión anterior como una evaluación nueva de eficacia.

Los avisos de estilo se registran en DD088, para después de todas las capacidades
principales. Siguen pendientes la evaluación humana, otros perfiles/material real,
seguridad y licencias, datos históricos, recuperación restante, aceptación completa
de12 páginas y revisión final. No se declara una nueva suite global verde.
