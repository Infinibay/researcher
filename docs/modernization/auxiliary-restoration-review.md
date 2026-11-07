# Cálculos locales y autoridad tras restaurar una instalación

Base `3a07b11`. Bloque **2026-11-07 17:27:42–17:48:42 UTC**, **21 min hasta
validar y cerrar el servidor**. La documentación y el checkpoint posteriores
quedan fuera de ese tiempo.

Se corrigieron dos fallos funcionales: una autorización local pendiente podía
copiarse y consumirse desde otra base sin decisión nueva; además, restaurar por
segunda vez copiaba `enrollment.json` al lugar activo y bloqueaba la inscripción
de la nueva copia. Ambos se reprodujeron antes de corregir el producto.

La migración63 vincula permisos nuevos a la identidad física de SQLite que ya
usa PeerRegistry. Los permisos anteriores sin origen se conservan pero no
autorizan una sucesora aún no ejecutada. Una vista del recibo distingue autoridad
actual e historia; el JSON original no cambia. La selección del cálculo recupera
resultados existentes o usa un permiso actual, sin adoptar permisos copiados.

La inscripción verificada de restore archiva los cálculos dentro de su propia
transacción. Conserva estado, resultados y consumo, retira los grants anteriores
y permite una decisión nueva sobre la copia. **No prueba que terminó el host
original.** La web explica esa diferencia. Otra restauración vuelve a requerir
autoridad nueva y archiva las inscripciones anteriores como evidencia.

## Qué se comprobó

- **136 casos distintos de fuente** durante el bloque, con el fallo de segunda
  restauración corregido y después verificado. La selección final del paquete
  instalado pasa **182/182,0 fallos,0 omisiones**, fuera del checkout y sin modo
  editable. Coinciden643 archivos Python/SQL,342 de producto;262 módulos backend
  importados desde la instalación.
- Backup, restore y enrollment reales sobre datos sintéticos: identidad local
  ausente, kernel registrado distinto y creación incompleta permiten una
  decisión nueva sobre la copia inscrita, manteniendo incierto el original.
  El kernel distinto de estos casos es metadata controlada; no se afirma un
  nuevo reinicio real de VM en este bloque.
- Un permiso copiado no admite trabajo antes ni después de inscribir la copia.
  Recuperar su recibo lo muestra histórico. Una decisión nueva crea otra
  sucesora; el consumo original de3000ms permanece y25ms nuevos llevan el total
  a3025ms. La base original no cambia.
- Una segunda copia no hereda permisos de la primera. Los resultados guardados
  siguen recuperables sin nuevos workers. La inscripción anterior queda archivada
  byte por byte, sin bloquear la nueva.
- Interrupción dentro de la transacción de enrollment revierte el archivo local
  y deja la instalación inactiva. Migración62→63 preserva recibos originales sin
  inventar origen. La inversa usada se rechaza y la cadena incluye interrupción
  de63 antes del commit.
- **13 pruebas DOM,2 contratos del cliente y build pasan**. El cliente distingue
  un recibo histórico de una autorización actual y conserva identidad tras
  respuesta perdida.
- Navegador sobre frontend compilado y API instalada después de un restore/
  enrollment real: **4 estados,1 autorización,9 comprobaciones**, sin errores de
  página. La barrera general de cambio de instalación conserva/archiva primero
  el packet anterior; luego se permite una decisión nueva. El POST confirma y
  pierde la respuesta; recargar recupera el recibo mediante GET, sin otro POST.
  [Capturas y límites visuales](../design/audits/2026-11-07-local-restoration/report.md).
- SQLite final: original con1 cálculo/1 permiso/0 archivos; copia con el mismo
  cálculo,2 permisos y1 archivo.3000ms desconocidos en ambas;0 runs/dispatches en
  esa fixture, integridad correcta. La autorización no ejecutó el cálculo.
- **50 módulos/definiciones Python relevantes tienen docstrings**; JSDoc del
  recibo actualizado.301 archivos/85 candidatos de prompts,85 revisados y0
  pendientes. No cambió texto generativo. Cero turnos de modelo; el encoder
  preparado se ejerció offline en la selección instalada.

## Errores del ensayo y límites

El primer test reprodujo el consumo indebido del permiso copiado. La prueba de
segunda restauración encontró el archivo de inscripción activo; se corrigió
su ubicación, conservándolo como evidencia. El primer DOM reprodujo el mensaje
incorrecto al recuperar un permiso histórico y pasó tras separar su alcance.

El navegador inicial esperaba llegar directamente al control local con un packet
viejo sin identidad de instalación. La barrera existente lo impidió correctamente,
sin escrituras. El ensayo se adaptó para archivar explícitamente el packet antes
de entrar, sin cambiar la barrera. Una invocación posterior usó un directorio de
trabajo incorrecto y no inició el navegador; la corrida final se hizo contra el
mismo servidor y estado, con una sola autorización real.

La recuperación de identidades inciertas usa una copia separada e inscripción
nueva. **No se habilitó un bypass de cierre en el original**, ni se adoptan sus
procesos, grants o planes. La copia no incluye escrituras posteriores al snapshot
ni establece una cuota global entre varias instalaciones. No se atribuye al
worker consumo total del host, Ken, administración o proveedor.

E08 sigue abierto hasta contrastar el conjunto de consumos observables y sus
límites.41 de43 escenarios amplios siguen abiertos,0/12 páginas completamente
aceptadas y la última suite global conserva fallos conocidos. No se realizó
evaluación de comprensión humana; la revisión de capturas no la sustituye.
DD111 conserva la mejora de la explicación genérica del panel para el final.

[Procedimiento operativo](../operations/local-calculation-recovery.md),
[resultados](auxiliary-restoration-results.json), [paquete](auxiliary-restoration-packaging.json),
[docstrings](auxiliary-restoration-docstrings.json).
