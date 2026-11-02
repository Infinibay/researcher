# Hallazgos: registro con evidencia

Se eligió el índice persistente con lector amplio entre tres conceptos independientes
y una adaptación móvil. La tabla posponía la lectura y el dossier duplicaba metadatos.
La selección fue delegada por el usuario; las imágenes son referencias de diseño, no
fuentes de investigación. [Procedencia](../../concepts/findings/manifest.json).

El estado anterior tenía nueve elementos con infracciones de contraste detectadas en
escritorio y móvil. Mostraba porcentajes declarados sin explicar suficientemente su
procedencia; buscar texto podía descartar los otros filtros y el detalle resolvía IDs
sin proyecto. Los lectores nuevos aplican alcance explícito y filtros combinados,
conservan valores históricos y distinguen citas de evaluación acreditada.

La [verificación funcional](interaction-evidence.json) pasó 18 estados en navegador:
índice y paginación completa de 57 registros sin duplicados; filtros combinados;
evaluación heredada desplegable; captura exacta y HTML literal; foco de ida/vuelta;
declaraciones históricas paginadas; recuperación de 21 citas y una limitación al final
de un texto largo; encoder local real sobre 57 hallazgos, continuación ligada a hashes
y selección explícita de uno; indisponibilidad/reintento; móvil, enlaces/IDs ajenos y
lectura pendiente durante un cambio de proyecto. No hubo turnos de investigación.

Los 18 estados no registraron errores de página ni infracciones axe. La lectura también
se comprueba a 1440, 390 y 320 px en [el smoke](smoke-evidence.json). El lector queda dentro
del viewport; escritorio permite desplazar el índice y el documento por separado.
Se inspeccionaron capturas reales; el resultado no acredita comprensión humana ni
compatibilidad exhaustiva con lectores de pantalla o aceptación de la ruta completa.

El verificador necesitó correcciones: una etiqueta compuesta no coincidía con el
locator exacto aunque el probe ARIA sí mostraba “Tipo”; se normalizó el marcado sin
afirmar un fallo demostrado de lector de pantalla. La navegación de fragmentos debía
esperar el cuerpo y la posición nuevos antes de volver a pulsar. El fallo503 simulado
debía cubrir el reintento automático configurado. El selector de proyecto es un botón
con opciones, no un select nativo. Se conservaron resultados parciales válidos sobre
los mismos inputs al retomar esas comprobaciones. Estas fallas del verificador no se
presentan como defectos corregidos de la aplicación.

Los [invariantes](binding-evidence.json) comprueban que hallazgos/citas, informe,
fuentes, referencias, revisiones Wiki y cantidades de ejecuciones permanecieron
intactos en la copia sintética. La generación de investigación estaba prohibida por
un guardia. Los pesos semánticos son locales y fijados; no hubo embedding remoto.

Pendiente: revisión independiente realmente admitida, consumidores antiguos,
invalidez de dependencias tras correcciones, pruebas con personas, lector de pantalla,
zoom/estado de sesión y aceptación integral. Hallazgos suma un piloto al terminar sus
verificaciones de entrega; siguen 0/12 páginas completamente aceptadas.
