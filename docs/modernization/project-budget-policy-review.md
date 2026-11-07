# Revisión explícita del presupuesto

Bloque iniciado el **7 de noviembre de2026 a las15:57:53UTC**, después de`ca9a7ad`.
Se implementó la decisión del propietario en backend y en el panel existente:
versión esperada, recibo estable, recuperación de respuesta perdida y conservación
de consumo. [Contrato](../architecture/project-budget-policy.md).

Validación observada completa a las **16:15:50 UTC**, **17 min 57 s hasta validar**.
Pasan97casos distintos de backend y47instalados fuera del checkout, sin omisiones.
Coinciden629archivos entre fuente, wheel e instalación,332de producto;227módulos
backend se cargaron desde el entorno instalado. El frontend compila; pasan8casos
DOM y2contratos. El inventario mantiene85candidatos revisados y0pendientes.
La documentación y el checkpoint posteriores no están incluidos en esa duración.

## Evidencia

- Pruebas de SQLite: creación previa al primer turno, modificación de política
  histórica, competencia entre editores, recibo original tras cambios posteriores,
  disminución por debajo del consumo e identidad/valores inválidos.
- Un hijo termina abruptamente después de escribir política y recibo, antes del
  commit. Ambos cambios se revierten; la misma decisión puede enviarse después.
- Migración60 repetible conserva las políticas originales en revisión0. La inversa
  sin uso conserva esos valores; con decisiones guardadas se rechaza. Se extendió
  la prueba de caída de escritores a todas las migraciones18–60.
- API real rechaza solicitudes sin sesión, con bearer de herramienta y sin CSRF.
  El propietario puede guardar y recuperar el recibo sin runtime configurado;
  no se crean ejecuciones por esa operación.
- Host con kernel/broker/SQLite reales: primero rechaza el intento por presupuesto;
  cambiar la política no envía un turno. Una solicitud posterior separada usa la
  capacidad nueva y queda `needs_review`, con cero aceptaciones y peers cerrados.
  [Observaciones](project-budget-policy-native-observations.json).
- Ocho casos DOM y dos contratos del cliente pasan. Cubren recarga tras pérdida
  de respuesta, conflicto, respuesta tardía de otro proyecto, fallo de almacenamiento
  local, paquete corrupto y recibos con ámbito/versión/contenido incorrectos.
- Navegador sobre frontend compilado, API y SQLite reales: cuatro estados,
  dos escrituras explícitas y recuperación mediante GET tras perder una respuesta
  ya confirmada en el servidor. La reserva desconocida100se conserva al bajar el
  total a50; no aparecen ejecuciones nuevas. [Recorrido](../design/audits/2026-11-07-project-budget/report.md).

[Resultados y hashes](project-budget-policy-results.json),
[verificación instalada](project-budget-policy-packaging.json).

Se corrigieron errores de preparación de pruebas: un parámetro indirecto no
cambiaba el esquema de la fixture, el estado esperado de la entrega documental
era `needs_review` y los límites numéricos del ensayo de migración aún terminaban
en59. La declaración TypeScript del recibo usó inicialmente una extensión no
admitida de un tipo indexado; se corrigió antes de validar UI/build. Los recibos
de estos fallos permanecen y no se presentan como defectos productivos descubiertos.

Trece módulos/definiciones Python relevantes se comprobaron con docstrings; los
componentes y helpers nuevos tienen JSDoc. Tres candidatos de prompt sin cambios
se revalidaron contra el diff de su consumidor SQLite. No se cambió el catálogo
ni se realizó una nueva evaluación de eficacia con modelos.

## Límites y siguiente bloque

Guardar no despacha trabajo ni cambia autorizaciones existentes. Un plan ya
autorizado puede usar la nueva capacidad en futuras admisiones normales; no se
promete congelar todo el proyecto mientras se edita su presupuesto.

No se consumieron modelos: la generación/Ken del ensayo nativo son controlados.
La medición de cuota/facturación sigue desconocida. El panel móvil es operable,
pero su densidad y encuadre de capturas se registraron enDD108para la pasada final.
No se declara aceptación integral de las páginas ni nueva suite global verde.

Siguiente trabajo principal: contrastar la aceptación completa de E07/E08,
incluidas cadenas de revisión y llamadas auxiliares, con los controles ya
implementados. No repetir lo cerrado por detalles de estilo. El plan completo
sigue activo con42escenarios amplios abiertos y0/12páginas totalmente aceptadas.
