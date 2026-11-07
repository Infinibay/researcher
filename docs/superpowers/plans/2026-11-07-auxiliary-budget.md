# Presupuesto durable del procesamiento local

Inicio: **2026-11-07 16:34:39 UTC**. Plan principal: actualización del proyecto,
E08. Se mantienen primero las capacidades principales y los detalles al final.

## Contrato y decisión

Hoy PDF/otros parsers y semántica tienen límites por proceso y una plaza compartida,
pero sus consumos no quedan agregados por proyecto. Se añadirá un registro común
en el límite de transporte del worker, antes de crear el hijo. Las entradas de
fuentes/hallazgos nativos, hallazgos del propietario, captura y preview deben
vincular explícitamente proyecto/autoridad; una variable de contexto se limita
al tramo síncrono que invoca ese transporte, no a toda la solicitud HTTP.

La identidad del cálculo comprende bytes de entrada, tipo, política y versión de
productores/dependencias. Un resultado guardado de esa identidad se reutiliza
sólo dentro del mismo proyecto y después de revalidar la autoridad. No se repite
un cálculo cuyo recibo quedó incierto. Reutilizar resultados completos cambia
deliberadamente la reconstrucción anterior en cada consulta; nunca mezcla
vectores, versiones o páginas de otro corpus.

Se reservan una operación y el techo de CPU del hijo; al terminar, la medición
válida puede sustituir el techo. Si falta, se conserva la reserva y se dice
desconocido. Se registra tamaño de entrada, actor/intento y resultado original.
Los cupos son acumulados por proyecto y por intento nativo. El propietario podrá
revisar los totales del proyecto en el editor ya existente, con su versión/recibo;
eso no borra consumo, reanuda trabajo ni repite cálculos inciertos.

No se convierte CPU/vectores en tokens de generación, ni se afirma medir toda la
CPU del servicio, la cuota interna de Codex o la calidad del encoder. La
recuperación física de un worker incierto conserva sus requisitos de operación.

## Trabajo y comprobación

- [x] Migración61, inversa sólo sin uso y registro transaccional por cálculo.
- [x] Cupos por proyecto/intento, recibos completos reutilizables y reservas
  desconocidas persistentes; conflictos/concurrencia/cancelación/reinicio.
- [x] Transporte común y las cinco entradas autenticadas, incluidos cambios de
  formato del parser; consumo visible por API sin un runtime generativo activo.
- [x] Edición de límites auxiliares en la decisión existente y presentación web
  con ejemplo de reserva; conservar packets antiguos y respuesta perdida.
- [x] Pruebas de SQLite real, HTTP, worker real y paquete instalado; comprobar
  docstrings, prompts afectados, build y recorrido web pertinente.
- [x] Actualizar inventario, cobertura, tablero, tiempos y checkpoint local.

Compatibilidad: las decisiones de presupuesto antiguas conservan exactamente su
payload/recibo; omitir campos auxiliares no cambia su política. Datos previos no
se convierten en mediciones cero. Una instalación sin historial empieza con la
política explícita predeterminada, sin inventar trabajo anterior.

Resultado: bloque validado el2026-11-07a17:00:19UTC;25min40s. Ver `docs/modernization/auxiliary-budget-review.md`. El plan principal y E08 siguen abiertos por la recuperación explícita del cálculo incierto.
