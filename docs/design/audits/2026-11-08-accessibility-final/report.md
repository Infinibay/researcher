# Accesibilidad: nombres, encabezados y reflujo corregidos

Las doce rutas completan **24 transiciones por teclado**, a1440 y320px, con
**cero infracciones Axe de página completa y cero desbordamientos interiores**.
Esta comprobación cierra DD106/DD107 por el alcance medido. El zoom nativo y la
evaluación con lector de pantalla siguen pendientes; no se declara conformidad
WCAG ni comprensión humana.

Base `d1d505b`. Trabajo iniciado8noviembre2026 a20:13:17UTC; comprobaciones leídas
a20:23:46UTC: **10min29s**. Documentación/checkpoint posteriores aparte.
[Resultados](../../../modernization/accessibility-final-results.json),
[baseline](baseline-evidence.json), [final](final-evidence.json),
[recibo HTTP/SQLite](final-result.json).

## Causas y cambios

| Hallazgo reproducido | Causa comprobada | Cambio |
|---|---|---|
| Nombre accesible del contador,24estados | El nombre omitía el número visible | Incluye contador, conserva99+ y ofrece el total real; al abrir se limpia y conserva el estado pulsado |
| Índice móvil de Informes sin h1 | El único h1 estaba dentro del lector oculto | El índice sin selección tiene h1; al elegir un informe, el título del documento conserva esa responsabilidad |
| Cuatro índices desbordan a320px | Margen−24px frente a relleno16px: workbench336px/main scroll328px | Margen−16px por debajo del mismo breakpoint700px; workbench/main320px |
| Anterior/Siguiente de recibos | Sus nombres usaban «anteriores/siguientes», omitiendo el texto visible exacto | «Anterior: bytes de…» y «Siguiente: bytes de…», conservando contexto y deshabilitación |

La comparación incluye mediciones geométricas de antes/después; la causa del
reflujo ya no se presenta como una hipótesis sin comprobar. No se recorta el
desbordamiento ni se ocultan controles para pasar el ensayo. Se añadieron ocho
JSDoc ingleses al módulo de recibos, sus funciones y componentes relevantes.

## Pruebas y límites

- RED:14contratos pasan/2fallan y1caso Header pasa/2fallan por los defectos
  buscados. El recorrido previo termina exit1 por cuatro desbordamientos, registra
  el nombre incorrecto24veces y el h1 ausente una vez.
- GREEN: **167contratos y80pruebas UI**, suite web completa, sin fallos.
  Build correcto; conserva el aviso anterior de chunks grandes.
- El recorrido final usa el servidor instalado y SQLite reales, sin respuestas
  API inventadas: dos proyectos, grupo/hito, tareas con dependencia y una corrección
  conservada tras recarga. Cero runs, despachos o turnos; integridad `ok` después
  del cierre del servicio original. Código de salida del servicio143 conservado.
- Skip link, las24rutas, foco dentro del contenido, cierre del menú al navegar y
  Escape con retorno al disparador pasan. El gate ya rechaza también hallazgos
  Axe; antes los registraba pero filtraba al decidir su resultado.
- La paginación usa DOM del componente real renderizado, con ambas salidas y
  controles habilitados/deshabilitados. No se repite una ejecución para probar
  este cambio de nombres. No es un ensayo interactivo completo del recibo.
- ESLint dirigido devuelve1por `no-control-regex` en el filtro intencional de
  controles de terminal. El mismo archivo en `d1d505b` reproduce la misma regla;
  se conserva como DD161. No se declara lint verde ni se modifica ese filtro.

El primer comando con `-I` impidió importar el módulo hermano del evaluador y no
inició un host. Dos intentos posteriores se detuvieron por selectores obsoletos
del guion: «Épica» pasó a «Grupo» con opciones dentro del label, y la dependencia
es ahora un checkbox. Se corrigió el guion según la interfaz y el formulario
actuales antes de medir el producto. También se conserva un lanzamiento de
contratos desde cwd incorrecto; la corrida RED válida usa `frontend`.
Los registros originales se guardan en esta carpeta. Los cuatro hosts creados
cerraron y sus bases quedaron íntegras, sin inferencias.

Varias rutas contienen índices vacíos sintéticos; sus estados con contenido,
errores y ejecución mantienen la evidencia previa, sin renovarla por este ensayo.
Se inspeccionaron visualmente los cuatro móviles afectados y el escritorio de
Informes, además de Documentos/Informes antes del cambio. El resto conserva
capturas y mediciones automáticas, sin atribuirle una nueva revisión visual.
El host del navegador integrado sigue indisponible; se usa el fallback Playwright
del repositorio autorizado previamente.320px CSS no equivale a zoom nativo ni a
lector de pantalla. U08 humano, Ken/ONNX y el cierre global siguen abiertos.

## Capturas finales

| Ruta |320px|1440px|
|---|---|---|
| Resumen |[Móvil](320-overview.png)|[Escritorio](1440-overview.png)|
| Proyectos |[Móvil](320-projects.png)|[Escritorio](1440-projects.png)|
| Planificación |[Móvil](320-epics.png)|[Escritorio](1440-epics.png)|
| Tareas |[Móvil](320-tasks.png)|[Escritorio](1440-tasks.png)|
| Agentes |[Móvil](320-agents.png)|[Escritorio](1440-agents.png)|
| Conversación |[Móvil](320-chat.png)|[Escritorio](1440-chat.png)|
| Documentos |[Móvil](320-wiki.png)|[Escritorio](1440-wiki.png)|
| Hallazgos |[Móvil](320-findings.png)|[Escritorio](1440-findings.png)|
| Informes |[Móvil](320-reports.png)|[Escritorio](1440-reports.png)|
| Archivos |[Móvil](320-files.png)|[Escritorio](1440-files.png)|
| Repositorios |[Móvil](320-repositories.png)|[Escritorio](1440-repositories.png)|
| Ejecución |[Móvil](320-flow.png)|[Escritorio](1440-flow.png)|

Antes: [Documentos](before-320-wiki.png), [Hallazgos](before-320-findings.png),
[Informes](before-320-reports.png), [Archivos](before-320-files.png).

Los logs se conservan literalmente, incluidos 42 diagnósticos de espacios/final
de archivo de `git diff --check`. Fuera de esos logs, la comprobación pasa.
