# Recuperación explícita de cálculos locales

Base `f65ed71`. Tramo medido de continuación: **2026-11-07 17:08:08–17:24:28
UTC, 16 min 20 s hasta validar y cerrar el servidor de prueba**. La exploración
anterior no tenía inicio recuperable y queda fuera; documentación/checkpoint
posteriores tampoco se atribuyen a ese tramo.

El usuario puede consultar un cálculo sin resultado, saber si su dueño y su
trabajador siguen activos y autorizar una sucesora cuando el cierre está
comprobado. Autorizar no ejecuta trabajo: la próxima solicitud idéntica, con
permisos vigentes y capacidad suficiente, usa una nueva reserva. El consumo
original y los resultados posteriores conservan sus identidades.

La migración62 añade identidad de ejecución y decisiones de continuación. El
transporte guarda la identidad del hijo antes de entregarle datos y registra
cierre después de esperar su salida física. Se reutilizan primitivas pidfd,
inicio del proceso, kernel y namespace del runtime; no se crea otro dueño ni
se trata un parser ordinario como namespace-init. La decisión es única por
operación original y recuperable por su clave tras perder una respuesta.

## Evidencia y escenarios comprobados

- **105 casos distintos de fuente** a lo largo del bloque; los grupos se
  solapan. La selección instalada final pasa **136/136, sin fallos ni omisiones**,
  incluidos los16 casos nuevos. Coinciden639 archivos Python/SQL entre fuente,
  wheel e instalación,339 de producto;241 módulos backend importados desde la
  instalación no editable, fuera del checkout.
- Dueño vivo: no admite sucesora. Dueño muerto y trabajador todavía vivo:
  tampoco. Un hijo real termina después de retirar su dueño y permite continuar
  sólo cuando el pidfd demuestra su cierre. No se usa un timeout como prueba.
- Proceso real que muere tras reservar: mantiene3000ms pendientes. Después de
  una autorización y un resultado de25ms, quedan3025ms contabilizados.
- Transporte real: registra el hijo antes de liberar entrada; el primer hijo
  falla, una autorización permite exactamente otro y el resultado nuevo se
  reutiliza sin un tercer proceso. Dos solicitudes concurrentes consumen la
  misma autorización una sola vez.
- Resultado todavía por guardar: aun con el trabajador cerrado, un dueño vivo
  conserva la posibilidad de confirmar su recibo; no se autoriza otro cálculo.
- Segunda interrupción: requiere otra decisión sobre la sucesora exacta;
  paginación e historia conservan las generaciones anteriores.
- Permiso retirado o cupo insuficiente: autorizar no los elude ni crea un intento
  nativo. Dos decisiones de propietario compiten por una sola sucesora. Un
  registro de otro proyecto no se puede consultar ni autorizar.
- API real con sesión/CSRF: ni ausencia de sesión ni bearer de herramientas
  autorizan. Recibos originales se recuperan sin runtime configurado.
- Migración61 con trabajo desconocido: preserva consumo sin inventar identidad.
  Cadena de migraciones incluye62, interrupciones y guardas de inversa usada.
- **12 pruebas DOM,2 contratos del cliente y build pasan**. Navegador con API
  instalada y SQLite reales:3 estados,1 escritura,7 comprobaciones; la respuesta
  se pierde después del commit y la recarga recupera el recibo sin otro POST.
  Conserva1 cálculo/3000ms y1 autorización; no inicia trabajo. Tres capturas
  inspeccionadas,0 violaciones Axe en el componente y sin overflow externo en
  los tamaños observados. [Informe visual](../design/audits/2026-11-07-local-continuation/report.md).
- **74 módulos/definiciones Python relevantes documentados**; módulos y funciones
  nuevas del cliente tienen JSDoc. Inventario:299 archivos,85 candidatos de
  prompts revisados,0 pendientes. No cambió texto generativo.

Se usó el encoder local preparado offline en la comprobación instalada. **Cero
turnos de modelo** y ningún gasto de suscripción en este bloque. El servidor y
todos los procesos de comprobación finalizaron antes del checkpoint.

## Errores del ensayo y alcance abierto

Los contratos iniciales fallaron por ausencia del módulo/backend y del componente
web. El primer test DOM de recuperación esperaba un único argumento de la función
mock; React Query también pasa su contexto. Se corrigió la aserción para comprobar
el packet original, conservando el comportamiento del producto y el log inicial.

**E08 sigue abierto.** Registros antiguos sin identidad, observación desde otro
kernel/namespace y muerte durante creación antes de guardar la identidad del
hijo quedan explícitamente inciertos. Conectar esos casos con evidencia de cierre
de la instalación/restauración existente es un pendiente funcional, no un detalle
de presentación. No se añadió un bypass ni se borró ninguna reserva.

La CPU medida sigue siendo la del worker; no acredita toda la CPU/red del host,
Ken, administración o consumo interno del proveedor. Las capturas y Axe no
demuestran comprensión humana ni aceptación integral de páginas. DD110 registra
etiquetas, locale y densidad para el final. Permanecen41 de43 escenarios amplios
abiertos,0/12 páginas completamente aceptadas y la última suite global con fallos;
esta selección no sustituye esas obligaciones ni sustenta un porcentaje global.

[Contrato](../architecture/auxiliary-work-budget.md), [resultados](auxiliary-continuation-results.json),
[paquete](auxiliary-continuation-packaging.json), [docstrings](auxiliary-continuation-docstrings.json).
