# Agentes — piloto conectado al runtime nativo

Resultado del alcance visual/funcional: **passed**. Aceptación integral pendiente.
[Concepto elegido](../../concepts/agents/brief.md), [manifest](../../concepts/agents/manifest.json).

La página anterior dependía de `/api/agents`, roster y contadores del engine viejo.
Ahora consulta ejecuciones nativas por proyecto, con actor/tarea/intento, modelo
registrado, consumo observado y paginación. Añade Stop sobre la identidad original
y enlace a tarea/historial; no introduce otro motor de parada. El endpoint antiguo
sigue existiendo para consumidores pendientes de migrar: no se declara eliminado.

## Evidencia y alcance

- Cuatro casos nuevos backend observados RED por método/ruta ausentes; después,
  19 casos seleccionados pasan en6.43s (`test_agent_runs`, `test_question_inbox`,
  `test_inference_journal`). SQLite real, lectura autenticada sin runtime,
  aislamiento de proyectos, cursor, máximo acumulado sin doble conteo, Stop
  sin fingir cierre y consumo ausente. Cero inferencias reales.
- `node tests/agents.browser.mjs` desde frontend con Vite5179: ocho capturas
  finales a1440/390px, además de la inicial;0incidencias Axe en la región nueva,
  0erroresJS/desbordamientos. [Recibo](evidence.json).
- HTTP controlado: lectura sin escrituras, enlace original, paginación,
  intento aún no registrado/consumo desconocido, Stop503 conservando estado,
  Stop202 sin afirmar cierre, cambio de proyecto, consulta503 y reintento.
  Dos POST de Stop intencionales del ensayo, cero efectos sobre datos del usuario.
-123testsfrontendPASS1.955s; TypeScript/VitePASS3.94s. Advertencia heredada de
  tamaño de bundle; no se añade dependencia. No se repitió suite global ni wheel:
  el último wheel instalado anterior no contiene esta nueva proyección.
- Seis definiciones Python nuevas y diez definiciones nombradas TS/JS auditadas,
  todas documentadas en inglés; módulos con documentación. Ver
  [Python](python-docstrings.json) y [JSDoc](jsdoc.json).

## Comparación visual

Se abrieron las tres referencias y la adaptación móvil, además de las capturas
reales01/02/02b. Se conservan el índice, detalle, tipografía editorial y paleta.
Escritorio de concepto1487×1058 frente a viewport1440×1024; móvil de concepto
853×1844 frente a viewport390×1024. No se afirma equivalencia píxel a píxel.
En móvil el detalle y el control tienen capturas separadas con desplazamiento;
la cabecera global ocupa altura adicional. Los datos de ejemplo de la imagen no
se convierten en datos de producto. Contraste seleccionado pasa Axe; los estados
se explican con texto. No se observaron bloqueos funcionales P0/P1/P2 en este ensayo.

DD043 conserva densidad/jerarquía y agrupación secundaria para después de todas
las capacidades principales. La interacción humana, lector de pantalla, zoom,
otros motores y recorrido con runtime real siguen en aceptación integral.

## Límites y correcciones del ensayo

La captura inicial tuvo que esperar el vacío real «No agents yet»: el fixture no
contenía roster antiguo, aunque sí registros nativos para la futura página.
Se corrigió el directorio de salida de una invocación del verificador; se movieron
sus dos artefactos al proyecto y se retiraron sólo sus directorios vacíos.
Un intento de escritura no se aplicó por rutas relativas incorrectas; se verificó
su rechazo y se escribieron los archivos en el worktree correcto antes de probar.
El recorrido final detectó que el initScript del fixture sobrescribía el proyecto
en cada recarga: ahora sólo inicializa almacenamiento ausente. Esa corrección no
modificó el producto. El recorrido pasó después; todos los procesos observados
terminaron y el servidor de ensayo fue cerrado.

La proyección ofrece el intento actual y cantidad histórica por ejecución; no
suma consumos desconocidos ni pretende cubrir todo el historial presupuestario.
El detalle de intentos anteriores y presupuesto global conserva su bloque principal.
