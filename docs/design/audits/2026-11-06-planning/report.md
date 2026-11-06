# Planificación — piloto funcional

Resultado: **piloto verificado; aceptación integral pendiente**.
[Selección y contrato](../../concepts/planning/brief.md),
[imágenes, prompts y hashes](../../concepts/planning/manifest.json).

La ruta ahora ofrece propuestas nativas y grupos existentes en un índice, con
lectura de bases/suposiciones/criterios y dependencias. Las propuestas enlazan a
project/task/planRun originales; la lectura no acepta ni ejecuta. Se conservan
creación manual de grupos/hitos y eliminación confirmada, con errores visibles.
La selección y formularios se desmontan al cambiar de proyecto.

Pruebas: `node tests/planning.browser.mjs` desde frontend con Vite en5179.
Datos HTTP controlados, cero turnos nativos o efectos sobre datos del usuario.
Ocho estados capturados con Axe en la región nueva, más captura/aseveraciones de
foco/Axe del diálogo: nueve capturas finales, además de la captura inicial.
Cero incidencias Axe y cero erroresJS. Antes de las acciones manuales se comprueba
que las consultas no envían escrituras. Se ensayan POST rechazado422 con borrador
conservado, creación de grupo/hito, cancelación y confirmación del borrado, lectura
de dependencia y plan original, error parcial sin falso vacío y cambio de proyecto.
[Recibo](evidence.json).123testsfrontendPASS2.02s; build4.19s.14funciones nombradas
nuevas/modificadas con JSDoc,0faltantes ([auditoría](jsdoc.json)).

El primer verificador tuvo un error de sintaxis corregido antes de capturar la
pantalla inicial. Luego la prueba roja demostró la ausencia de la nueva superficie.
Axe detectó que dos aria-label omitían metadata visible; se retiraron los nombres
sustitutorios y se conservaron nombres derivados del contenido. El recorrido final
pasa. No se repitieron pruebas backend ni se certificó recuperación de POST perdido.

Comparación visual: escritorio1487×1058 frente a viewport1440×1024; móvil853×1844
frente a viewport390×1024, densidad1. Se abrieron referencia/capturas juntas y se
comparó composición y legibilidad, no exactitud píxel a píxel. La captura móvil
superior se complementa con desplazamiento a dependencias y decisión original.

- Tipografía: Georgia en títulos, sans existente en cuerpo; tamaños14–36px. No
  fuente remota ni iconos/avatares nuevos. Jerarquía de índice y lectura conservada.
- Espacio: índice18rem y detalle amplio en escritorio; un panel por vez en móvil,
  botón de retorno con restauración de foco. Densidad/altura compartida quedaDD042.
- Color: tokens existentes papel/tinta/verde; controles y error por texto además
  de color. Contraste verificado en las regiones de este recorrido.
- Imágenes: referencias de diseño archivadas, no controles rasterizados. Casillas
  del mock sustituidas deliberadamente por estados de lectura para evitar una
  falsa acción de aceptar resultados.
- Contenido: cantidad de tareas marcadas, sin porcentaje de cumplimiento; criterios
  propuestos separados de resultados; bases con origen y suposiciones visibles.
  Dependencias ausentes sólo tras consulta correcta, fallos se muestran como fallos.

La aceptación completa requiere navegación con backend real, recuperación y
protección de historia del CRUD, matriz completa de estados/zoom/lector de pantalla
junto a las otras rutas y evaluación humana. Las APIs CRUD preexistentes no tienen
operation_key: el borrador y aviso no equivalen a idempotencia. Ese cierre sigue
principal, no se esconde como pulido ni se declara resuelto por estas capturas.
