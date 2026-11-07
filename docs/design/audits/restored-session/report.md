# Aviso de cambio de instalación

Se revisó el aviso existente de acceso ampliado para una base restaurada.
La pantalla explica qué cambió, conserva solicitudes/borradores, ofrece una
descarga y exige una elección explícita antes de preparar trabajo nuevo.
El ejemplo de una publicación cuyo resultado podría estar sólo en el host/remoto
original distingue ausencia de evidencia y repetición autorizada.

Tres estados comprobados en Chromium: escritorio1440px, móvil390px y error de
almacenamiento. Escritorio/móvil no tienen hallazgos Axe ni desbordamiento
horizontal; las dos capturas se inspeccionaron visualmente. Se verificó el JSON
descargado y la conservación del paquete ante falta de espacio. No hubo escrituras
HTTP ni errores JS. La entrada explícita tras archivar también tiene prueba DOM.

Capturas: [escritorio](desktop.png), [móvil](mobile.png),
[almacenamiento no disponible](storage-refusal.png).
[Resultados](results.json), [harness](../../../../frontend/tests/restored-session.browser.mjs).

El primer ensayo del harness interceptó por error un módulo de Vite bajo
`/src/api/`; se limitó el mock a `/api/` y el ensayo original cerró su navegador.
Los tres estados aprobados corresponden al ensayo posterior corregido.
Las respuestas de sesión son controladas: no se afirma aquí backend real,
inferencia, calidad científica ni aceptación completa de ninguna de las12páginas.
