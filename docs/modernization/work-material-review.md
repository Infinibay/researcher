# Evidencia selectiva y antecedentes grandes

El esquema5 mantiene los requisitos actuales visibles y convierte secciones
históricas mayores a32768bytes en referencias verificables. Los lectores de
investigación y contexto permiten inspeccionar una estructura y seleccionar
valores JSON exactos, sin copiar cuerpos ajenos a la pregunta. Los originales
permanecen completos y se revalidan en cada lectura. Se conservan entregas2–4 y
políticas2–7; la política nueva8 explicita qué se leyó y qué sigue desconocido.
[Contrato y ejemplo](../architecture/selective-work-material.md).

## Validación

Bloque15:09:37–15:25:17UTC del7noviembre2026: **15min40s hasta validar**.

-87casos distintos de fuente pasan. La primera corrida de almacenamiento pasa50;
  la ampliación pasa8, dos nuevos. La regresión nativa/contexto/políticas tuvo
  34aprobados y1fallo de preparación del nuevo ensayo; su corrección pasa por
  separado. [Resultados y recibos](work-material-results.json).
-62casos instalados pasan fuera del checkout.622archivos coinciden entre fuente,
  wheel e instalación;329son de producto.246módulos backend se importaron desde
  el entorno instalado. [Recibo](work-material-packaging.json).
- Un contexto original de plan mayor a1MiB deja una entrada menor a25KB y
  conserva una restricción al final. Los paquetes de investigación de más de1MiB
  permiten recuperar limitaciones, una afirmación y su fuente en tres lecturas
  pequeñas. Una parte completa no se presenta como el paquete completo.
- Una continuación autorizada conserva la identidad del intento anterior;
  cancelar el consumidor retira el acceso. Índices de61hijos se recorren en
  páginas de25/25/11 sin revelar cuerpos ni afirmar haberlos leído. Se rechazan
  rutas inexistentes, selectores inválidos y consumidores sin entrega.
- El ensayo con kernel, broker, Git y SQLite reales registra entradas de4262 y
  5326bytes, con82630bytes de contexto referenciado. Autor y desarrollador leen
  665bytes seleccionados cada uno. El desarrollador recibe3072bytes de evidencia
  frente a399538bytes de informes. Hacen11 y12solicitudes reales de herramientas,
  con límite configurado25. Peers cerrados, origen`fact.txt=137`intacto y cero
  aceptaciones de código. [Observaciones](work-material-native-observations.json).
-51definiciones de seis módulos productivos tienen docstring. El inventario
  reproducible tiene85candidatos revisados y ninguna revisión pendiente.

El primer ensayo físico dejó un marcador no versionado en el repositorio de
origen. El desarrollo exige un origen limpio y se detuvo con`RunConflict`antes
del turno del hijo. El modo selectivo se trasladó a la configuración del proceso
controlado; los ensayos de fuente e instalación pasan sin relajar esa protección.
El fallo inicial y su recibo se conservan; no se cuenta como defecto productivo corregido.

## Siguiente trabajo funcional del engine

**Actualización posterior:** el fallo se reprodujo y corrigió en el
[bloque de presupuesto de herramientas](host-tool-budget-review.md). El texto
siguiente conserva el hallazgo que originó ese trabajo; ya no es un pendiente
de implementación. La aceptación completa de E07/E08 sigue abierta.

**Observado:** `CodexSession` cuenta inicios en`item/started`, mientras atiende
`item/tool/call`por otra rama. El generador controlado de estos ensayos emite las
peticiones, pero no esos avisos. Por eso se agregó un contador independiente de
peticiones reales en el hijo; no se usa el contador de avisos como prueba de ellas.

**Por comprobar:** que el límite duro cubra peticiones de herramientas aun si
faltan, se duplican o llegan tarde los avisos de inicio, sin contar dos veces
una misma llamada ni permitir un efecto adicional después del límite. Hay que
reproducirlo con el protocolo real de la sesión antes de elegir el cambio.
Se registra como trabajo funcional deE07/E08, no como pulido diferido.

No se ha usado la suscripción ni otro modelo. La generación y Ken son controlados;
no se demuestra comprensión humana ni calidad de selección de un modelo real.
Tampoco se declara aceptación global deC04, páginas o suite: quedan42escenarios
amplios abiertos y0/12páginas completamente aceptadas. Las entradas actuales de
tarea/conversación conservan sus límites explícitos; no se truncan silenciosamente.
