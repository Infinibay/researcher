# Capacidad real de lector preparada

Orca43.1 recibe eventos AT-SPI de Chromium156.0.8078.4, anuncia un control y un
aviso dinámico de una página sintética y entrega ambas frases a espeak-ng mediante
Speech Dispatcher0.11.4. Se comprobó la finalización de síntesis de las dos frases
antes de continuar/cerrar. **Es preparación de herramientas, no aceptación del
producto con lector.** [Resultados](../../../modernization/reader-capability-results.json).

El entorno es un contenedor rootless con D-Bus privado y Xvfb. Las teclas Tab y
Return proceden de X mediante xdotool, por lo que pasan por el lector; no se
confunden con entradas CDP que llegan directamente al navegador. Se montaron
sólo los módulos de prueba, node_modules, binarios de Chromium de sólo lectura y
una carpeta nueva de resultados. Sin cuenta, base, perfil ni D-Bus del operador.
No se instaló software en el escritorio ni se cambió su configuración.

El log de Orca registra «Revisar fuentes push button.» y el aviso sobre la fuente
sin fecha. El de Speech Dispatcher conserva el SSML entregado al módulo, sus
eventos END y206bloques de audio generado,16bit/mono/22050Hz. La salida ALSA es
nula: no hay evaluación auditiva humana ni prueba de dispositivo físico. El
perfil usa voz predeterminadaen-us y roles en inglés; se preserva el texto español,
pero no se acredita su pronunciación/localización. Los cuatro procesos originales
—Chromium, Orca, Speech Dispatcher y Xvfb— cerraron con salida0; el contenedor
también terminó con salida0 y fue retirado.

La documentación oficial de [depuración de Orca](https://orca.gnome.org/debugging)
explica el registro de eventos y salidas habladas; los parámetros de preferencias
y habla están en su [manual](https://gnome.pages.gitlab.gnome.org/orca/help/introduction.html).
El servidor de voz usa los parámetros descritos en
[Speech Dispatcher](https://manpages.debian.org/bookworm/speech-dispatcher/speech-dispatcher.1.en.html).
Aquí se verifican logs del lector y del sintetizador reales, además del cambio
visible del DOM causado por Return; no sólo el árbol accesible o etiquetas DOM.

## Intentos y límites preservados

- El primer intento falló antes de iniciar Orca/Chromium porque no existía el
  ejecutable gsettings. Se utilizó la API Gio.Settings ya instalada, sin añadir
  herramientas globales. [Recibo original](initial/result.json).
- El segundo mostró generación del anuncio del botón en Orca, pero Return llegó
  tan rápido que lo interrumpió antes de su entrega al sintetizador. El aviso sí
  se sintetizó. No se admite como síntesis completa de ambas frases.
  [Recibo y logs](speech-interrupted/result.json).
- El definitivo espera SSML de la frase concreta y END del módulo antes de la
  siguiente tecla y del cierre. [Recibo](speech-complete/result.json),
  [log Orca](speech-complete/orca-debug.log),
  [log de síntesis](speech-complete/speech-logs/speech-dispatcher.log),
  [verificador](verify.py). El diagnóstico inicial de Orca sin ventana activa,
  anterior a la apertura de Chromium, se conserva; los anuncios posteriores
  demuestran que encontró el control y el aviso.

La imagen de herramientas se construyó en37,835s y queda identificada por su
SHA256 en los resultados. No es una nueva imagen del producto ni resuelve sus
dependencias Ken/ONNX. La caché temporal de Podman pertenecía a otro arranque;
se confirmó ausencia de procesos del prefijo y se preservaron sus directorios
runtime antes de regenerarlos. No se borró el almacenamiento de imágenes.

Los logs se conservan con el formato original de Orca/SSIP/apt, incluidos sus
espacios y saltos finales;2513diagnósticos de espacios quedan sólo en esos logs.
El diff fuera de logs no presenta avisos.

## Siguiente comprobación

Aplicar el lector al host instalado con los datos sintéticos ya usados: identidad
de las doce rutas, controles y contenido de tareas/correcciones. Emparejar antes
de iniciar el log del lector para no registrar el código privado. Esperar salidas
reales de Orca y síntesis, sin inferirlas de la sola presencia de un nodo.

Siguen pendientes esa evaluación del producto, U08 humano, elección Ken/ONNX,
documentación relevante restante y cierre integrado. Se mantienen42/43escenarios
y12/12páginas por alcance; esta capacidad no incrementa esas aceptaciones.
