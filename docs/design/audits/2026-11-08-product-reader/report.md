# Lectura real del espacio de trabajo

Las doce rutas permiten recorrer su enlace, un control del contenido y el
encabezado mediante teclado nativo con **Orca 51.1**. El lector también lee las
dos frases del ejemplo guardado en una tarea. Se verificaron **50 comprobaciones
de frase en 50 frames distintos con síntesis terminada**, más el rol de encabezado
de nivel 1 en las doce páginas. [Resultados](../../../modernization/product-reader-results.json),
[verificación de los logs](verification-final.json), [recibo del host](final/result.json).

Es una evaluación de lectura con este perfil de escritorio, no conformidad WCAG
universal. **Falta comprobar el mismo acceso a explicaciones enriquecidas y
diagramas.** No establece comprensión humana, pronunciación adecuada en español,
audio físico, interacción con todos los formularios, móvil ni otros lectores.
U08 sigue abierto y se mantienen los 42/43 escenarios amplios.

## Qué se comprobó

- Host real instalado, HTTP y SQLite reales; dos proyectos sintéticos, dos tareas,
  dependencia y ejemplo del propietario conservados. Sin respuestas API simuladas
  ni una nueva llamada de inferencia del producto.
- Chromium 156.0.8078.4 visible en Xvfb privado, viewport de 1280 × 900; Node
  24.22.2, Orca 51.1/revisión 244bdadd9, AT-SPI 2.62.1 y Speech Dispatcher 0.12.1.
  [Inventario del entorno](final/browser/tool-packages.txt). La imagen local queda
  identificada por SHA256 en los resultados.
- Tab y Return enviados por X mediante xdotool. Se compara el foco DOM con el
  evento de foco adquirido y procesado por Orca. Documentos enfoca legítimamente
  su h1; las otras once rutas enfocan main. No se fuerza el foco por JavaScript.
- Lectura del nombre accesible del control. Se obtiene la expectativa con
  `ariaSnapshot`; eso **no constituye prueba de habla**: se exige además la salida
  real de Orca y el texto enviado al módulo de síntesis con su evento END.
- Modo de lectura permanente mediante Insert+A triple, su anuncio completo y la
  búsqueda del siguiente h1 mediante la tecla 1. Esto conserva la separación
  entre lectura y uso de formularios. Son comandos documentados en
  [Orca](https://gnome.pages.gitlab.gnome.org/orca/help/commands_reading.html).
- La corrección se lee con KP Plus, comando Say All de escritorio. Se exige el
  SSML emitido por el backend de Orca y las dos frases sintetizadas hasta END.
  [Vista de la tarea](final/browser/owner-correction.png). Esta comprobación abre
  Tareas explícitamente después del recorrido SPA; no rescata una ruta fallida.

La síntesis produce audio hacia ALSA null. No se ha escuchado físicamente ni se
ha evaluado su inteligibilidad; las etiquetas y el texto español se conservaron,
con roles/voz predeterminados en inglés. El guion no sustituye lectura real por
la existencia de un nodo en el árbol accesible.

El código local de emparejamiento se introduce **antes de arrancar Orca** y no
aparece en los logs del pase final. Orca, navegador, voz y Xvfb cerraron con salida
0; el contenedor y su retirada terminaron con 0. Se observó la salida 143 del
supervisor original después de SIGTERM. Los registros de negocio e inferencia
que inspecciona `observe` permanecen iguales: cero runs, dispatches y native_starts,
e integridad SQLite ok. **Es igualdad de esa proyección, no del archivo SQLite ni
de todas sus tablas.** [Observaciones antes/después](final/result.json).

## Fallos retenidos y decisiones

[Las diez ejecuciones](runs.json) se conservan por separado. Los nueve intentos
anteriores no incrementan la aceptación final.

| Hallazgo | Decisión y evidencia |
|---|---|
| El aviso de traducción de Chrome retenía Tab fuera de la aplicación | El idioma/flags no lo eliminaron; se cierra con Escape nativo y se conserva la captura de la ventana completa |
| Orca 43.1 conserva un encabezado eliminado al cambiar de página | Incluso esperando el evento de foco, Proyectos falla por navegación SPA y se lee al recargar. Se conserva como fallo; la recarga diagnóstica siempre relanza el error original y nunca acepta la ruta |
| El entorno Debian de herramientas anterior llevaba un lector antiguo | Se ensayó un entorno actual con Orca 51.1, manteniendo los mismos binarios de Node/Chromium y la misma aplicación. También cambian sus bibliotecas del sistema: no es una comparación causal exclusiva de Orca |
| Cambiaron CLI, versión y delimitadores de logs del lector | Se reconoce la versión real, se usan sus argumentos vigentes y se identifican eventos procesados de ambas familias de formato |
| El lector entraba en modo de formulario desde un selector | Se alcanza y escucha un control real del contenido antes de cambiar explícitamente al modo de lectura. No se modifican controles, ARIA ni cachés de la aplicación para obtener el pase |
| Documentos enfoca su título en vez del contenedor | Se exige el evento real del nodo actualmente enfocado dentro de main; no se impone un destino distinto al legítimo de la página |
| El texto DOM de «Nueva página» incluía un ＋ decorativo oculto a lectores | La expectativa usa el nombre accesible, conservando obligatorios los dos productores de habla y END |
| El borrador usaba un atajo de lectura continua incorrecto | El pase final usa KP Plus, conforme al manual; no se da por comprobada la corrección con Insert+Down |

La investigación del lector antiguo se contrastó con las fuentes oficiales de
[43.1](https://github.com/GNOME/orca/blob/ORCA_43_1/src/orca/structural_navigation.py#L783)
y [51.1](https://github.com/GNOME/orca/blob/51.1/src/orca/structural_navigator.py#L1293).
Orca 48 mantiene el mecanismo relevante; no se construyó otro entorno 48 como
supuesto arreglo. El pase actual no elimina el fallo observado con 43 ni promete
compatibilidad con esa versión.

## Evidencia y reproducción

[Guion del host](../../../../evals/operation/screen_reader.py),
[contenedor del lector](../../../../evals/operation/screen_reader_container.py),
[guion del navegador](../../../../frontend/tests/screen-reader-audit.mjs),
[verificador independiente](../../../../evals/operation/verify_screen_reader.py).
Las tres fuentes nuevas ejecutadas coinciden con sus copias retenidas. El índice web es
el mismo build del pase de zoom anterior. No cambió código de la aplicación en
este bloque ni se declara una nueva suite global de backend.

Los logs originales están comprimidos sin pérdida; el
[manifiesto](raw-artifact-manifest.json) registra SHA256 de bytes originales y
almacenados. El verificador volvió a aprobar leyendo esas copias comprimidas.
Comprueba de manera independiente habla, identidad/estado de foco y los roles h1;
el guion ejecutado verifica además los delimitadores completos de procesamiento
del evento de foco. [Revisión independiente](independent-review.md).

Con assets e instalaciones de prueba ya preparados, el recorrido se reproduce
sin usar datos históricos del operador:

```sh
podman build --pull=missing --network=host -t localhost/researcher:reader-current -f evals/operation/Containerfile.reader evals/operation

/path/to/installed-python evals/operation/web_workspace.py --assets /path/to/assets.json --node /path/to/node --output /tmp/NEW-workspace --journey workspace

/path/to/installed-python evals/operation/screen_reader.py --fixture /tmp/NEW-workspace --output /tmp/NEW-reader --chromium /path/to/chrome-linux64

python evals/operation/verify_screen_reader.py --evaluation /tmp/NEW-reader --output /tmp/NEW-reader-verification.json --require-current-source
```

Las rutas de salida deben ser nuevas. `--container-spec` admite el prefijo
rootless de herramientas usado en este entorno; no cambia las cuentas ni instala
software en el escritorio. La receta usa repositorios de Arch: reconstruirla en
otra fecha puede actualizar paquetes. El recibo identifica la imagen y versiones
observadas, sin prometer una reconstrucción idéntica desde repositorios móviles.

Primer archivo de entradas: 22:38:29,621 UTC; recibo final: 23:06:09,370 UTC del
8 de noviembre: **27 min 39,749 s** entre esos archivos. Incluye investigación,
fallos y actualización del entorno. La preparación inicial y la documentación
posterior quedan fuera. El pase final, entre sus entradas y recibo, ocupa 45,657 s.

## Lo que continúa

Contenido explicativo enriquecido y diagramas con lector; documentación relevante
frontend/C; U08 humano y decisión Ken/ONNX; detalles diferidos y aceptación final
coherente de paquete, suite global y revisión independiente. No hay push, merge
ni despliegue en esta entrega.
