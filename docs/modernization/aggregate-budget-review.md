# Presupuesto coherente y rechazo comprensible

El bloque iniciado el **7 de noviembre de 2026 a las15:46:39UTC** contrasta E07/E08
con la implementación real. Ya existían reserva durable por intento, cupo acumulado
por proyecto y máximos de consumo en SQLite. No se reemplazó esa contabilidad.

Se corrigieron dos problemas reproducidos: la sesión podía reducir su consumo
mostrado al recibir un aviso atrasado, y el rechazo por presupuesto del proyecto
se explicaba como fallo genérico del runtime. Ahora la sesión conserva su máximo
acumulado y el error específico lleva los números originales de la decisión.
Un intento que requiere reservar100tokens frente a un límite99 queda guardado
sin enviar un turno, sin snapshot de entrada y sin proponer ningún resultado.

## Validación

Validación observada completa a las **15:56:22 UTC**, **9 min 43 s** desde el
inicio. Pasan113casos distintos de fuente en su última observación y65instalados
fuera del checkout, sin fallos ni omisiones en la corrida instalada. Coinciden
625archivos entre fuente, wheel e instalación,329de producto;224módulos backend
se importaron desde el entorno instalado. El inventario conserva85candidatos
revisados y ninguna revisión pendiente. El cierre documental posterior no está
incluido en la duración hasta validar.

## Casos comprobados

- Avisos40,70,10,60 dejan70tokens observados y un incremento máximo de40. El
  resultado nativo y el presupuesto adjunto a una respuesta de herramienta
  coinciden. Duplicados y un aviso menor en un turno posterior no devuelven cupo.
- Dos conexiones SQLite compiten simultáneamente por un último turno. Sólo una
  reserva; la otra recibe el motivo y snapshot de agotamiento. La admisión sigue
  siendo transaccional; este ensayo confirma el control existente.
- Reiniciar el coordinador conserva la reserva de un turno sin medición. Otra
  solicitud no obtiene un turno nuevo; el historial distingue desconocido de0.
- El host completo prepara y cierra sus procesos reales, pero un presupuesto
  insuficiente impide enviar `turn/start`. Quedan cero despachos de inferencia,
  propuestas, aceptaciones, informes y permisos activos.
- Un hijo real emite50notas de razonamiento sin trabajo. El intento termina por
  tiempo sin progreso, explica esa causa y conserva la reserva de1000tokens como
  consumo desconocido. No se genera un resultado ni otro turno; todos los peers
  y permisos quedan cerrados. Generación y Ken son controlados en estos ensayos.

[Observaciones del host](aggregate-budget-native-observations.json),
[resultados y hashes](aggregate-budget-results.json),
[paquete instalado](aggregate-budget-packaging.json).

La primera reproducción tuvo cinco fallos y un aprobado. Un ensayo posterior
de sólo razonamiento falló por un `import time` ausente en la nueva rama de la
fixture: el hijo se desconectaba antes de sostener las notas. Se corrigió la fixture
y se repitió ese caso; no se cambió el producto para ocultar la desconexión.

Los cuatro módulos productivos y las seis definiciones nuevas/modificadas tienen
docstrings. Tres revisiones de prompts quedaron obsoletas por el hash del consumidor
SQLite: se contrastó su diff, se verificó que los candidatos no cambiaron y se
actualizó la justificación. No se inventa una nueva evaluación con modelos.

## Siguiente capacidad principal

La búsqueda de `runtime_project_budgets` en Python del backend muestra una lectura
de historia y la inserción/comprobación de la primera reserva. No hay una operación
para cambiar explícitamente una política ya fijada. Cambiar la configuración del
host provoca un conflicto de reconciliación, sin borrar el historial. Se debe
añadir una decisión del propietario que revise límites con versión esperada y
recibo, mantenga el consumo y no relance intentos automáticamente. Esta capacidad
pertenece a E08; no debe resolverse reseteando presupuestos ni como un detalle visual.

Falta cerrar la aceptación integral de E07/E08 y los demás escenarios del plan.
Las observaciones siguen sin demostrar facturación exacta o cuota de suscripción;
no se modifica proveedor, no se consume un modelo real y no se declara una nueva
suite global verde. Siguen42escenarios amplios abiertos y0/12páginas completamente
aceptadas. Primero se terminan las capacidades principales y luego los detalles.
