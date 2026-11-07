# Presupuesto durable de auxiliares locales

Base `0b0fb4e`. Bloque **2026-11-07 16:34:39–17:00:19 UTC**, **25 min 40 s
hasta validar**; documentación/checkpoint posteriores quedan fuera de ese tramo.

Se implementó una capacidad compartida de procesamiento local para usuario y
agentes. La migración61 conserva operación original, actor/intento, entrada,
techo de CPU, consumo observado/desconocido y resultado recuperable. El
transporte reserva antes de arrancar el worker y mantiene el cierre físico.
Semántica y parsers comparten los cupos del proyecto; el intento nativo tiene
también su propio techo. [Contrato y límites](../architecture/auxiliary-work-budget.md).

Un resultado completo de los mismos bytes/productores se reutiliza dentro del
proyecto sin recalcular. Se verifica su hash y se revalida la autoridad. La
respuesta distingue reutilización y medición del cálculo original: no atribuye
esa CPU a una ejecución nueva. Un cálculo sin resultado permanece incierto,
con su reserva, sin replay automático ni una falsa medición cero.

Las cinco entradas autenticadas quedan conectadas: fuente nativa, hallazgos
nativos/del propietario, captura documental y preview. Cambiar formato del
parser conserva la contabilidad. Los límites locales se leen y editan desde el
presupuesto existente, con la misma revisión/operación durable. Los packets
anteriores siguen válidos; omitir los nuevos campos conserva la política local.

## Qué se comprobó

- 105casos distintos de fuente a lo largo del bloque. Los grupos se solapan y
  no se suman sus tamaños. La comprobación instalada final cubre119casos,
  **119pasan,0fallan,0omitidos**, con634archivos iguales entre fuente/wheel/
  instalación,335de producto y237módulos importados de la instalación.
- SQLite real: competencia por el último cupo, techo del intento, identidad
  original, aislamiento, grant revocado incluso al recuperar un resultado,
  reducción por debajo del consumo, decisión antigua compatible e inversa sin uso.
- Un proceso real muere después de confirmar su reserva: al reiniciar se
  conserva todo el techo y no se recalcula. La cadena de migraciones incluye
  interrupción real de61antes de su commit y recuperación de la misma base.
- HTTP/worker reales: preview humano y captura nativa comparten una extracción;
  hallazgos del usuario/agente comparten un cálculo del encoder preparado. Otra
  fuente/consulta sin cupo se rechaza antes de abrir proceso o registrar fuente.
- Stop de un parser ocupado espera su salida física y mantiene4000ms como
  consumo desconocido. No se confunde cancelación con ausencia de recursos usados.
- 9pruebas DOM,3contratos TypeScript y build frontend pasan. El recorrido web
  real verifica respuesta perdida/recarga/recibo y reducción por debajo del
  consumo con dos escrituras; [capturas y evidencia](../design/audits/2026-11-07-auxiliary-budget/report.md).
- 66nodos relevantes Python con docstrings;296archivos/85candidatos del inventario
  de prompts,85decisiones vigentes. No cambió texto generativo ni se consumieron
  turnos de modelo; el encoder local sí se ejecutó offline.

## Correcciones y límites de la evidencia

La primera corrida del contrato falló al faltar el módulo nuevo. Una selección
posterior apuntó a un nombre de test inexistente y no ejecutó casos; se corrigió
la selección. El test HTTP nuevo buscaba `message` donde el contrato devuelve
`detail`; la respuesta429y la ausencia de proceso ya eran correctas. Se corrigió
el test, conservando logs. El primer paquete pasó119casos; se repitió la
verificación tras añadir el origen explícito de la medición reutilizada.

Una aserción visual demasiado amplia aceptó el valor anterior durante refetch.
Se corrigió a igualdad exacta y se verificó de sólo lectura el mismo estado;
no se repitieron las operaciones. El móvil sigue parcialmente recortado por el
contenedor y queda enDD108. Pluralización y estado transitorio de refresco se
registran enDD109para la pasada final; no se rediseñó ahora el panel.

**E08 continúa abierto:** falta diagnóstico/continuación explícitos de un
cálculo sin resultado recuperable. No se debe resolver con un retry automático
ni borrando su reserva. Este es el siguiente trabajo principal. Medir CPU del
worker tampoco acredita cuota de todo el host, red, Ken o administración.
Persisten recuperación/storage, datos históricos, evaluaciones humanas/modelos,
aceptación de12páginas, dependencias y distribución.41de43escenarios siguen
abiertos; la suite global con fallos no se reemplaza por esta selección.

[Resultados y grupos](auxiliary-budget-results.json),
[paquete final](auxiliary-budget-packaging.json),
[docstrings](auxiliary-budget-docstrings.json).
