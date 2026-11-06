# Ejecución — inspector nativo y controles originales

Resultado del alcance visual/funcional: **passed**. Aceptación integral pendiente.
[Selección](../../concepts/flow/brief.md), [referencias](../../concepts/flow/manifest.json).

La nueva página deja de representar fases fijas de MainProjectFlow. Consulta los
planes aceptados y el grafo/entregas nativos; identifica dependencias, resultados
previos recibidos, impedimentos y entregas históricas. El enlace de intervención
conserva proyecto/tarea; el del plan conserva también planRun. Los controles son el
componente PlanExecution existente, con el mismo almacenamiento y transporte.
No cambia backend, protocolos, coordinación ni autoridad.

## Verificación

La prueba inicial falló por ausencia de la nueva página, tras capturar la antigua.
El primer recorrido implementado pasó. Se añadió comprobación del título móvil y
navegación a un prerrequisito con entrega histórica, y se verificó la versión final.

`node tests/flow.browser.mjs` desde frontend con Vite5179: **diez capturas finales**
a 1440/390 px, más la inicial. Cero incidencias Axe seleccionadas, errores JavaScript
o desbordamientos en la región nueva. [Recibo](evidence.json).

- Dependencias reales; navegación al prerrequisito y su entrega histórica fallida.
- Conteo de entregas actuales excluye la historia; contexto obsoleto no muestra
  avance vigente; sin manifest las dependencias son explícitamente desconocidas.
- Plan aceptado sin autorización no se representa como ejecución iniciada.
- Pausa con respuesta503 conserva el paquete. Tras recargar, reenviar conserva
  exactamente cuerpo y operation_key. El recibo no se presenta como cierre físico.
- Leer no envía POST; los dos POST del ensayo son la misma pausa explícita.
- Cambio de proyecto desmonta la selección; consulta503 no se interpreta como vacío.

Datos HTTP controlados, cero modelos/procesos recuperados/datos reales del usuario.
El servidor de ensayo no tenía backend WebSocket; sus errores de proxy no son
prueba de salud de red ni errores JavaScript de la región. No se declara Stop físico.

**123 pruebas frontend pasan en 1,920 s; TypeScript/Vite en 4,01 s.** Doce
funciones/tipos nombrados documentados con JSDoc en inglés ([auditoría](jsdoc.json)).
Advertencia de bundle grande ya existente; ninguna nueva dependencia. Backend,
wheel, suite global y evaluaciones con personas no se repitieron en esta entrega.

## Comparación visual y límites

Se abrieron las tres alternativas y móvil junto con las capturas reales01/02/04.
Se conserva la composición índice/lista/inspector, jerarquía editorial y colores.
Los datos y acciones reales sustituyen los ejemplos de las referencias. Desktop
1487×1058 frente a viewport1440×1024; móvil de referencia registrado en el manifest
frente a viewport390×1024. No se afirma equivalencia píxel a píxel.

El control y la evidencia pueden requerir desplazamiento móvil; la captura02b lo
comprueba. La cabecera compartida y la densidad de los controles reutilizados se
registran como DD044, después de todas las capacidades principales. No se observan
P0/P1/P2 funcionales en este recorrido. Zoom, lector de pantalla, otros motores,
comprensión humana y escenarios reales de recuperación siguen pendientes.

Los 36 conceptos desktop y 12 móviles del proyecto tienen presencia, hashes,
prompts y selección comprobados en [la auditoría de artefactos](../../concept-artifact-audit.json).
Eso no equivale a aceptación integral de las doce páginas.
