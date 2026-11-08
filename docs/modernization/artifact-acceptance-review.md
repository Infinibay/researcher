# Decisión original visible en Informes

El resultado documental podía estar aceptado y su informe seguir apareciendo
únicamente como borrador: el catálogo leía el flag original, pero no la decisión
guardada. El filtro accepted no encontraba esos documentos. **Corregido sin
reescribir el informe o su estado de origen.**

La API añade `owner_acceptance` desde la propuesta/decisión inmutables del mismo
proyecto, tarea e informe. Incluye run, contexto, fecha y hash originales; la
vigencia se declara `not_rechecked`. El catálogo no carga el contenido para
compararlo. El detalle sí compara sus bytes actuales con la versión aceptada y
la interfaz avisa si difieren. Un flag accepted heredado no fabrica un recibo.

El filtro accepted incluye decisiones guardadas y flags históricos; draft excluye
los documentos incluidos en resultados aceptados sin cambiar su flag original.
La interfaz distingue «Aceptación guardada · vigencia por comprobar», documento
original y tarea donde consultar la decisión. No equivale a validez científica,
publicación o aceptación del contexto actual. El enlace conserva proyecto/tarea/
informe; no inventa soporte para un nuevo parámetro de navegación de runs.

Tres RED de propietario sobre SQLite/HTTP y dos RED de renderizado reproducen la
brecha. **35casos fuente,94instalados,150contratos y51UI pasan**, sin skips. El
primer intento de prueba tenía una clave de pairing incorrecta; se corrigió antes
de registrar el RED pertinente. No se presenta ese401como fallo de producto.

Paquete desde sdist limpio: **685Python/SQL coinciden**,365productivos; todos los
241imports backend de la selección proceden del entorno instalado. WheelSHA256
`ac90bf7978b02419fab107422fa28d6dabeb2518b1688a82e7a8ba64cb882727`.
pip check83paquetes, tipos/build pasan. Esquema69sin nueva migración.
17definiciones Python con docstrings y función nueva de UI con JSDoc. DosI001y
un any heredado en tipos quedan paraDD135/DD132; bundle enDD121, no estilo global verde.

El navegador real ya encuentra la aceptación por filtro, conserva borrador como
estado original y presenta fuentes y decisión separadamente. Datos del ensayo
sintéticos,0modelos generativos y0escrituras de negocio por abrir páginas.
[Resultados](artifact-acceptance-results.json), [paquete](artifact-acceptance-packaging.json),
[recorrido y límites](evidence-pages-review.md). No nueva suite global ni cierre deU08/C10.
