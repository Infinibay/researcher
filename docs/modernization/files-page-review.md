# Archivos: aceptación técnica y visual

La ruta `/files` completa sus operaciones con HTTP, SQLite y archivos reales en
instalaciones sintéticas nuevas. Se mantiene el concepto elegido **Archivo con
inspector**. El único cambio de producto de este bloque hace opcional el historial
confirmado: con 55 adjuntos empujaba el catálogo hasta 4858 px; ahora empieza a
649 px. Los intentos pendientes cargados siguen visibles y se puede consultar una
página anterior incluso cuando los primeros 50 intentos están pendientes.

El recorrido comprueba subida y descarga exacta, nombres iguales en proyectos
distintos, respuesta perdida con reintento del mismo envío y respuesta tardía tras
cambiar de selección. Recorre búsqueda y paginación, recarga, enlace de otro
proyecto, teclado y foco del diálogo de borrado. Las previas de texto, PDF de dos
páginas, DOCX, CSV, JSON y XML conservan identidad y procedencia; extraerlas no
guarda una fuente de investigación ni prueba que una tarea haya leído el adjunto.

Los fallos de publicación y borrado se inyectan con triggers SQLite en el host
desechable. Se recuperan los bytes completos del intento original. Otro original
se trunca expresamente: su recuperación se rechaza y cerrar el intento conserva
los cuatro bytes `PART`. Un borrado fallido conserva el original descargable; un
recibo perdido se consulta en el historial del mismo borrado. El coordinador
contrasta estos efectos desde el almacenamiento después del navegador.

Pasan 25 estados del recorrido final, 48 casos del backend instalado, 5 pruebas de
interacción y 5 contratos frontend, sin omisiones. Se conservan los fallos iniciales
y no se suman repeticiones como casos distintos. El backend del producto no cambió;
se reutiliza la rueda limpia que coincide con 676 fuentes. Build y ESLint de los
archivos TypeScript modificados pasan; sigue el aviso de bundle grande y el I001
ya registrado del evaluador. Cuatro definiciones Python modificadas tienen
docstrings en inglés; los módulos y helpers nuevos del navegador tienen JSDoc.

La inspección visual detectó que el primer ensayo complementario aceptaba una
lista transitoriamente vacía mientras cargaba, y luego regresaba al proyecto
anterior. Esas dos capturas se rechazan como prueba de vacío. El ensayo corregido
exige el proyecto elegido y el mensaje real de catálogo vacío. Mantiene los
65 adjuntos y 70 operaciones del ensayo original; sólo se creó un proyecto de
metadatos vacío, sin volver a subir ni borrar adjuntos. Los resultados de ambos
ensayos se conservan diferenciados.

Se acepta la operación técnica y la revisión visual delegada de esta página:
**2 de 12 páginas** junto con Documentos. DD127 conserva densidad móvil y mensajes
secundarios para después de las capacidades mayores. Los ejemplos son sintéticos;
no se afirma aceptación humana, zoom nativo ni lector de pantalla exhaustivo.
U08 sigue abierto. Cero runs, despachos o inferencias; los servidores cierran y
los guardianes registran cierre con retirada del dominio de recursos.

La contención del motor sigue siendo un pendiente principal; no se deduce su
solución del funcionamiento de Archivos. Permanecen 41 de 43 escenarios amplios
verificados y el resto del plan activo. No hay historial del propietario que
migrar, según su confirmación explícita.

[Resultados](files-page-results.json), [paquete](files-page-packaging.json),
[docstrings](files-page-docstrings.json), [auditoría visual](../design/audits/2026-11-08-files-acceptance/report.md),
[reproducción](../../evals/operation/README.md).
