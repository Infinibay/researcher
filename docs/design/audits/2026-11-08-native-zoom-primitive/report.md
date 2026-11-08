# Mecanismo de zoom nativo comprobado

Chromium **156.0.8078.4** aplica zoom nativo al 200 % y 400 % usando preferencias
de perfiles desechables. Se comprobó sobre HTML sintético, **no sobre las páginas
del producto**. No es aceptación de accesibilidad ni una prueba con lector de
pantalla. El propósito es disponer de un mecanismo verificable para el recorrido
pendiente, pese a que el host del navegador integrado no está disponible.

La exploración usa el mapa de zoom del perfil descrito por la
[implementación de Chromium](https://chromium.googlesource.com/chromium/src/+/lkgr/chrome/browser/ui/zoom/chrome_zoom_level_prefs.cc).
La fuente consultada es `lkgr`; no se pudo abrir el tag exacto del binario. La
comprobación del efecto se basa en las mediciones del navegador realmente usado,
no en suponer equivalencia entre versiones.

## Mediciones reales

La ventana exterior permanece en **1280 × 1024**. No se usa zoom CSS, transform,
emulación de viewport, `deviceScaleFactor` ni escala de página del protocolo.

| Zoom | Ventana CSS interior | `devicePixelRatio` | Zoom CSS raíz | Escala visual |
|---|---|---|---|---|
|100 %|1280 × 937|1|1|1|
|200 %|640 × 468|2|1|1|
|400 %|320 × 234|4|1|1|

Los controles comprueban el cambio de ancho CSS y la proporción de píxeles,
manteniendo la ventana exterior. Cada contexto y el servidor local se cierran;
ambos procesos de prueba terminaron con código 0. No se usaron perfiles del
operador, cuentas, modelos ni una instalación del producto.

[Resultado original](result.json), [programa](probe.mjs), [log](probe.log).

## Captura recortada detectada y corregida

La inspección visual detectó que `page.screenshot` guardaba imágenes de
1280 × 937, 640 × 468 y 320 × 234 respectivamente. Las dos últimas recortaban
el contenido ampliado: no permiten revisar una interfaz completa. Se conservan
literalmente como [100 %](zoom-1.png), [200 % recortado](zoom-2.png) y
[400 % recortado](zoom-4.png). El resultado original sólo verifica el mecanismo
de zoom; no validaba dimensiones de captura.

Una segunda comprobación a 400 % usa `Page.captureScreenshot` sin `clip`, con
`fromSurface=true` y `captureBeyondViewport=false`. Devuelve **1280 × 937**, igual
que el viewport observado en la métrica legacy del protocolo; se exige esa igualdad
y se vuelve a comprobar el viewport CSS 320 × 234, DPR 4 y zoom CSS/visual 1.
Se inspeccionó la imagen completa. No se retocaron ni reescalaron sus píxeles.

[Captura completa 400 %](full-zoom-4.png), [resultado](capture-result.json),
[programa](capture-probe.mjs), [log](capture-probe.log).

## Siguiente comprobación

Aplicar este mecanismo a las doce rutas del host instalado con datos sintéticos,
sesión de propietario real y sin iniciar agentes. Verificar navegación, foco,
acceso a controles y desplazamiento, además de ausencia de desbordamiento
horizontal. Las dimensiones CSS reales a 400 % son 320 × 234: el umbral histórico
de 160 px de alto de `main`, usado con viewport de 1024 px, no es por sí solo un
criterio normativo para este caso. Tampoco se debe ocultar un fallo funcional
real retirando un umbral: observar controles y contenido en el viewport efectivo.

No se añaden páginas aceptadas, conceptos de diseño ni escenarios cerrados por
esta prueba primitiva. La evaluación humana, la accesibilidad con lector, Ken/ONNX
y los controles finales conservan su alcance pendiente.
